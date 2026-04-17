"""Main bot orchestrator engine.

Central coordinator that ties together all subsystems: VAD, STT, TTS,
LLM, context management, and the Recall.ai meeting client. Manages
the full lifecycle of a bot session from joining to leaving a meeting.

Phase 6 implementation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.core.llm import LLMClient
from app.core.search import SearchClient
from app.meeting.recall_client import RecallClient, RecallClientError
from app.meeting.session import MeetingSession, SessionState
from app.utils.bot_profiles import get_persona_tts_voice
from app.utils.filler import FillerManager
from app.utils.prompt_builder import build_prompt_for_mode, resolve_persona_id
from app.core.insight_detector import contains_verifiable_claim, verify_claim
from app.utils.meeting_metrics import QuestionStageTimer
from app.utils.followup_markers import has_coherence_marker
from app.utils.tts_chunks import split_text_for_tts
from app.utils.wake_word import detect as detect_wake_word, is_directed_at_other

logger = logging.getLogger(__name__)

# Module-level constants for phrase matching
_STOP_PHRASES = (
    "thank you", "thanks", "that's enough", "stop", "okay stop",
    "ok stop", "shut up", "enough", "got it", "okay got it",
    "ok got it", "that's fine", "never mind", "nevermind",
    "okay thanks", "ok thanks", "thank you assistant",
)

_CORRECTION_TRIGGERS = (
    "correct", "wrong", "accurate", "fact check", "fact-check",
    "verify", "true", "false", "mistake", "error", "right",
    "is that", "are you sure", "double check", "double-check",
    "actually", "really", "correction",
)

_INSIGHT_CHECK_COOLDOWN_SECONDS = 30.0

def _log_task_exception(task: asyncio.Task) -> None:
    """Log unhandled exceptions from fire-and-forget background tasks."""
    if not task.cancelled() and task.exception():
        logger.error("Background task failed: %s", task.exception())


class BotEngineError(Exception):
    """Base exception for BotEngine errors."""


class SessionNotFoundError(BotEngineError):
    """Raised when a session_id is not found in active sessions."""


class BotEngine:
    """Orchestrates the AI meeting bot's full processing pipeline.

    Coordinates audio capture, speech detection, transcription, question
    detection, context assembly, LLM inference, speech synthesis, and
    audio playback in a real-time streaming loop.

    Heavy models (VAD, STT, TTS) are loaded lazily on first meeting
    join to keep startup fast and memory usage low until needed.

    Attributes:
        sessions: Dictionary mapping session IDs to MeetingSession objects.
    """

    def __init__(self) -> None:
        """Initialize the bot engine.

        Creates lightweight shared services. VAD, STT, and TTS are
        intentionally NOT loaded here — they are loaded lazily via
        ``_lazy_load_models()`` on the first ``join_meeting`` call.
        """
        self.sessions: dict[str, MeetingSession] = {}
        self._sessions_by_bot_id: dict[str, str] = {}  # bot_id -> session_id
        self._last_response_time: dict[str, float] = {}  # session_id -> timestamp
        self._last_speaker: dict[str, str] = {}  # session_id -> speaker who triggered last question
        self._followup_speakers: dict[str, set[str]] = {}  # session_id -> speakers heard during follow-up window
        self._pending_question: dict[str, dict] = {}  # session_id -> {question, speaker, timestamp}
        self._queued_question: dict[str, dict] = {}  # session_id -> question received during RESPONDING
        self._interrupted: dict[str, bool] = {}  # session_id -> True if participant interrupted bot
        self._insight_last_check: dict[str, float] = {}  # session_id -> last insight verification start time
        self._insight_inflight: set[str] = set()  # session_ids currently being verified
        self._question_collect_time: float = 0.5  # seconds to wait for user to finish speaking
        self._followup_window: float = 8.0  # seconds after audio finishes playing to accept follow-ups
        self._cooldown_seconds: float = 0.0  # no cooldown
        self._processing_lock: dict[str, asyncio.Lock] = {}  # session_id -> lock
        self._tts_lock: asyncio.Lock = asyncio.Lock()  # serializes TTS voice switch + synthesis across sessions
        self._recovery_lock_by_bot_id: dict[str, asyncio.Lock] = {}  # bot_id -> lock

        self._settings = get_settings()
        self._recall_client: RecallClient = RecallClient()
        self._llm_client: LLMClient = LLMClient()
        self._search_client: SearchClient = SearchClient()
        self._filler_manager: FillerManager = FillerManager()

        # Heavy model references — populated by _lazy_load_models()
        self._stt: Any | None = None
        self._tts: Any | None = None
        self._models_loaded: bool = False
        self._model_init_lock: asyncio.Lock = asyncio.Lock()

        # Per-session TTS instances so parallel meetings don't serialize
        self._session_tts: dict[str, Any] = {}

        self._vad_instances: dict[str, Any] = {}
        self._last_sentiment: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Per-session tracking helpers
    # ------------------------------------------------------------------

    def _ensure_session_tracking(self, session_id: str) -> None:
        """Populate all per-session tracking dicts for a session.

        Safe to call multiple times; only creates entries that are missing.
        """
        if session_id not in self._processing_lock:
            self._processing_lock[session_id] = asyncio.Lock()
        if session_id not in self._vad_instances:
            self._vad_instances[session_id] = None  # created on demand
        if session_id not in self._interrupted:
            self._interrupted[session_id] = False
        if session_id not in self._queued_question:
            self._queued_question[session_id] = {}

    async def _wait_for_processing_drain(self, session_id: str) -> None:
        """Block cleanup until any in-flight question handler finishes."""
        lock = self._processing_lock.get(session_id)
        if lock is None:
            return
        async with lock:
            return

    def _cleanup_session_tracking(self, session: MeetingSession) -> None:
        """Drop per-session caches only after question handling has drained."""
        session_id = session.session_id
        vad = self._vad_instances.pop(session_id, None)
        if vad is not None:
            vad.reset()
        self.sessions.pop(session_id, None)
        self._last_response_time.pop(session_id, None)
        self._last_speaker.pop(session_id, None)
        self._followup_speakers.pop(session_id, None)
        self._pending_question.pop(session_id, None)
        self._queued_question.pop(session_id, None)
        self._interrupted.pop(session_id, None)
        self._insight_last_check.pop(session_id, None)
        self._insight_inflight.discard(session_id)
        self._processing_lock.pop(session_id, None)
        self._last_sentiment.pop(session_id, None)
        self._session_tts.pop(session_id, None)
        if session.bot_id:
            self._sessions_by_bot_id.pop(session.bot_id, None)
            self._recovery_lock_by_bot_id.pop(session.bot_id, None)

    def wire_screen_capture(self, session: MeetingSession) -> None:
        """Attach a ScreenCaptureManager to a session."""
        from app.meeting.screen_capture import ScreenCaptureManager

        gemini_api_key = (self._settings.gemini_api_key or "").strip()
        if not gemini_api_key:
            raise BotEngineError(
                "GEMINI_API_KEY is required for screenshare capture and extraction."
            )

        from app.core.gemini import GeminiVisionClient
        gemini = GeminiVisionClient(api_key=gemini_api_key)

        session.screen_capture = ScreenCaptureManager(
            session_id=session.session_id,
            context_manager=session.context_manager,
            gemini=gemini,
        )
        logger.info("Screen capture enabled for session %s", session.session_id[:8])

    async def get_or_recover_session(self, bot_id: str) -> MeetingSession | None:
        """Return in-memory session for bot_id, or recover it from storage."""
        session_id = self._sessions_by_bot_id.get(bot_id)
        session = self.sessions.get(session_id) if session_id else None
        if session:
            if getattr(session, "screen_capture", None) is None:
                self.wire_screen_capture(session)
            return session

        lock = self._recovery_lock_by_bot_id.setdefault(bot_id, asyncio.Lock())
        async with lock:
            session_id = self._sessions_by_bot_id.get(bot_id)
            session = self.sessions.get(session_id) if session_id else None
            if session:
                if getattr(session, "screen_capture", None) is None:
                    self.wire_screen_capture(session)
                return session
            session = await self._recover_session(bot_id)
            if session is None:
                # Prune lock to prevent unbounded growth for unknown/inactive bot IDs
                self._recovery_lock_by_bot_id.pop(bot_id, None)
                return None
            return session

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    async def _lazy_load_models(self) -> None:
        """Initialize VAD, STT, and TTS models on first use.

        Called once before the first meeting join. Loads the Silero VAD,
        faster-whisper STT, and Kokoro TTS models into memory.

        Uses double-checked locking to prevent concurrent first-call
        races from loading models twice.
        """
        if self._models_loaded:
            return
        async with self._model_init_lock:
            if self._models_loaded:
                return

            logger.info("Loading audio processing models (first use)...")

            from app.core.stt import SpeechToText
            from app.core.tts import TextToSpeech

            self._stt = SpeechToText(model_size="large-v3", language="en", device="cpu")
            self._tts = TextToSpeech(
                voice=get_persona_tts_voice("general"),
                sample_rate=24000,
                speed=1.1,
            )

            # Pre-synthesize filler phrases now that TTS is available
            self._filler_manager.preload(self._tts)

            self._models_loaded = True
            logger.info("Audio processing models loaded successfully")

    # ------------------------------------------------------------------
    # Meeting lifecycle
    # ------------------------------------------------------------------

    async def join_meeting(
        self,
        meeting_link: str,
        agent_config: dict[str, Any],
    ) -> str:
        """Deploy the bot into a meeting.

        Creates a new session, deploys a Recall.ai bot to the meeting,
        and prepares the audio processing pipeline. The actual real-time
        audio loop runs as a background task.

        Args:
            meeting_link: The meeting URL (Zoom, Teams, or Meet).
            agent_config: Agent configuration including ``system_prompt``,
                ``mode`` ("general" or "custom"), ``agent_name``, and
                optionally ``description`` for custom agents.

        Returns:
            A unique session ID for tracking and controlling this session.

        Raises:
            BotEngineError: If bot creation or session setup fails.
        """
        # Ensure heavy models are loaded
        await self._lazy_load_models()

        # Build session
        meeting_id = meeting_link  # Use the link as the meeting identifier
        session = MeetingSession(meeting_id=meeting_id, agent_config=agent_config)

        # Build the system prompt (prefer persisted prompt; fallback for legacy records)
        mode = agent_config.get("mode", "general")
        persona_id = resolve_persona_id(mode, agent_config.get("persona_id"))
        description = agent_config.get("description", "")
        persisted_prompt = (agent_config.get("system_prompt") or "").strip()
        if persisted_prompt:
            system_prompt = persisted_prompt
        else:
            system_prompt = build_prompt_for_mode(mode, description, persona_id)
        session.agent_config["mode"] = "general"
        session.agent_config["persona_id"] = persona_id
        session.agent_config["voice"] = agent_config.get("voice")
        session.agent_config["system_prompt"] = system_prompt

        # Wire up the rolling summary with the LLM client
        session.context_manager.rolling_summary.set_llm_client(self._llm_client)

        # Wire up the RAG pipeline and load document summaries for this agent
        agent_id = agent_config.get("agent_id")
        if agent_id:
            from app.api.routes.documents import _get_rag_pipeline
            rag = _get_rag_pipeline(str(agent_id))
            session.context_manager.set_rag_pipeline(rag)

            # Load document summaries directly from database
            try:
                from app.models.database import Document, AsyncSessionLocal
                from sqlalchemy import select

                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Document).where(
                            Document.agent_id == agent_id,
                            Document.parsed.is_(True),
                            Document.doc_summary.isnot(None),
                        )
                    )
                    documents = result.scalars().all()
                    for doc in documents:
                        session.context_manager.add_document_summary(
                            doc.filename, doc.doc_summary
                        )
                    if documents:
                        logger.info(
                            "Loaded %d document summaries for agent %s",
                            len(documents), agent_id,
                        )
            except Exception as exc:
                logger.warning("Failed to load document summaries: %s", exc)

        self.wire_screen_capture(session)

        try:
            # Transition: PENDING -> JOINING
            session.transition(SessionState.JOINING)

            # Deploy bot via Recall.ai
            bot_name = agent_config.get("agent_name", "Synth")
            bot_id = await self._recall_client.create_bot(
                meeting_url=meeting_link,
                bot_name=bot_name,
            )
            session.bot_id = bot_id

            # Transition: JOINING -> LISTENING
            session.transition(SessionState.LISTENING)

            # Store the session and populate all per-session tracking dicts
            self.sessions[session.session_id] = session
            self._sessions_by_bot_id[bot_id] = session.session_id
            self._ensure_session_tracking(session.session_id)

            # Create a dedicated VAD instance for this session
            # (Silero VAD is stateful — sharing across sessions causes
            # cross-contamination of hidden state and speech boundaries)
            from app.core.vad import VoiceActivityDetector
            self._vad_instances[session.session_id] = VoiceActivityDetector(
                sample_rate=16000, threshold=0.5,
            )

            logger.info(
                "Bot joined meeting %s (session=%s, bot=%s)",
                meeting_link,
                session.session_id,
                bot_id,
            )

            return session.session_id

        except RecallClientError as exc:
            session.transition(SessionState.FAILED)
            logger.error("Failed to join meeting %s: %s", meeting_link, exc)
            raise BotEngineError(f"Failed to join meeting: {exc}") from exc
        except Exception as exc:
            session.transition(SessionState.FAILED)
            logger.error("Unexpected error joining meeting %s: %s", meeting_link, exc)
            raise BotEngineError(f"Unexpected error: {exc}") from exc

    async def stop_meeting(self, session_id: str) -> dict[str, Any]:
        """Stop the bot and leave the meeting.

        Gracefully shuts down the session, disconnects the Recall.ai bot,
        and returns the full transcript collected during the session.

        Args:
            session_id: The session ID returned by ``join_meeting``.

        Returns:
            Dictionary with ``transcript`` (full text) and ``summary``
            from the context manager.

        Raises:
            SessionNotFoundError: If session_id is not found.
        """
        session = self._get_session(session_id)
        session.session_end_requested = True

        # Transition to ENDED
        try:
            session.transition(SessionState.ENDED)
        except ValueError:
            logger.warning(
                "Session %s already in terminal state %s",
                session_id,
                session.get_state(),
            )

        # Disconnect the Recall.ai bot
        if session.bot_id:
            await self._recall_client.stop_bot(session.bot_id)

        # Let any in-flight question handler observe session_end_requested
        # and release the per-session lock before we remove shared state.
        await self._wait_for_processing_drain(session_id)

        # Collect transcript data before flushing
        full_transcript = session.context_manager.raw_buffer.get_full_text()
        summary = session.context_manager.rolling_summary.get_summary()

        # Flush remaining transcript chunks to RAG then cleanup
        session.context_manager.flush_remaining_embeddings()

        # Save meeting summary + structured entities for cross-meeting memory
        if session.bot_id and summary:
            with session.context_manager._state_lock:
                entities_snapshot = {
                    k: set(v) for k, v in session.context_manager._entities.items()
                }
            _task = asyncio.create_task(
                self._save_meeting_summary(session.bot_id, summary, entities_snapshot)
            )
            _task.add_done_callback(_log_task_exception)

        self._cleanup_session_tracking(session)

        logger.info(
            "Session %s ended (duration=%.1fs)",
            session_id,
            session.get_duration(),
        )

        return {
            "session_id": session_id,
            "transcript": full_transcript,
            "summary": summary,
            "duration_seconds": round(session.get_duration(), 2),
        }

    async def get_status(self, session_id: str) -> dict[str, Any]:
        """Get the current status of a bot session.

        Args:
            session_id: The session ID to query.

        Returns:
            Dictionary containing session state, duration, transcript
            length, and any error information.

        Raises:
            SessionNotFoundError: If session_id is not found.
        """
        session = self._get_session(session_id)
        info = session.to_dict()

        # Enrich with live metrics
        info["transcript_length"] = len(
            session.context_manager.raw_buffer.get_full_text()
        )
        info["summary_length"] = len(
            session.context_manager.rolling_summary.get_summary()
        )

        return info

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Return a list of all currently active session dicts.

        Returns:
            List of serialized session dictionaries for sessions
            in LISTENING or RESPONDING state.
        """
        return [
            session.to_dict()
            for session in self.sessions.values()
            if session.is_active
        ]

    def find_session_for_meeting(self, meeting_id: str) -> MeetingSession | None:
        """Return active session matching a meeting id."""
        for session in self.sessions.values():
            if session.meeting_id == meeting_id:
                return session
        return None

    def get_transcript_text(self, session_id: str) -> str:
        """Return full transcript text for a session when available."""
        session = self.sessions.get(session_id)
        if session is None:
            return ""
        return session.context_manager.raw_buffer.get_full_text()

    def submit_operator_instruction(self, session_id: str, instruction_text: str) -> None:
        """Store an operator instruction to steer upcoming responses."""
        session = self._get_session(session_id)
        cleaned = instruction_text.strip()
        if not cleaned:
            return
        session.operator_instructions.append(cleaned)
        session.last_instruction_at = datetime.now(timezone.utc)

    def set_session_muted(self, session_id: str, muted: bool) -> None:
        """Enable/disable operator mute for a session."""
        session = self._get_session(session_id)
        session.operator_muted = muted

    def request_stop_speaking(self, session_id: str) -> None:
        """Request immediate interruption of current/next spoken output."""
        session = self._get_session(session_id)
        session.output_stop_requested = True
        self._interrupted[session_id] = True

    def _ensure_tts_voice_for_persona(self, persona_id: str | None) -> None:
        """Switch TTS voice to the persona preset when needed."""
        if self._tts is None:
            return
        target_voice = get_persona_tts_voice(persona_id)
        if self._tts.voice == target_voice:
            return
        self._tts.voice = target_voice
        self._filler_manager.preload(self._tts)

    def _get_session_tts(self, session_id: str, persona_id: str | None = None) -> Any | None:
        """Get or create a per-session TTS instance.

        Each session gets its own Kokoro pipeline so parallel meetings
        don't serialize on a single TTS lock. Falls back to the shared
        instance if per-session creation fails. Returns ``None`` only
        if no TTS is available at all.
        """
        tts = self._session_tts.get(session_id)
        if tts is not None:
            target_voice = get_persona_tts_voice(persona_id)
            if tts.voice != target_voice:
                tts.voice = target_voice
            return tts

        try:
            from app.core.tts import TextToSpeech
            voice = get_persona_tts_voice(persona_id)
            tts = TextToSpeech(voice=voice, sample_rate=24000, speed=1.1)
            if tts._pipeline is None:
                raise RuntimeError("Kokoro pipeline failed to initialize")
            self._session_tts[session_id] = tts
            return tts
        except Exception as exc:
            logger.warning(
                "Per-session TTS init failed for session %s; using shared TTS: %s",
                session_id[:8],
                exc,
            )
            return self._tts

    def _should_cancel_output(self, session: MeetingSession) -> bool:
        """Return True when current output should stop immediately."""
        sid = session.session_id
        return (
            session.session_end_requested
            or session.output_stop_requested
            or self._interrupted.get(sid, False)
        )

    async def _synthesize_tts_audio(
        self,
        tts: Any,
        text: str,
        persona_id: str | None = None,
    ) -> bytes:
        """Synthesize audio, serializing access when using the shared TTS."""
        loop = asyncio.get_running_loop()
        if tts is self._tts:
            async with self._tts_lock:
                self._ensure_tts_voice_for_persona(persona_id)
                return await loop.run_in_executor(None, tts.synthesize, text)
        return await loop.run_in_executor(None, tts.synthesize, text)

    @staticmethod
    def _enqueue_playback_chunk(
        total_playback: float,
        playback_started_at: float | None,
        audio_bytes: bytes,
        *,
        sample_rate: int = 24000,
        now: float | None = None,
    ) -> tuple[float, float | None]:
        """Track queued playback from the moment audio is first sent."""
        if not audio_bytes:
            return total_playback, playback_started_at

        if playback_started_at is None:
            playback_started_at = time.time() if now is None else now

        chunk_duration = len(audio_bytes) / (sample_rate * 2)
        return total_playback + chunk_duration, playback_started_at

    @staticmethod
    def _remaining_playback_time(
        total_playback: float,
        playback_started_at: float | None,
        *,
        now: float | None = None,
    ) -> float:
        """Return queued playback time still expected to be audible."""
        if playback_started_at is None or total_playback <= 0:
            return 0.0

        current_time = time.time() if now is None else now
        return max(0.0, total_playback - (current_time - playback_started_at))

    async def _recover_session(self, bot_id: str) -> MeetingSession | None:
        """Recover a session for a bot_id by looking up the meeting in the DB."""
        try:
            from app.models.database import Meeting, Agent, AsyncSessionLocal
            from sqlalchemy import select

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Meeting).where(Meeting.bot_id == bot_id, Meeting.status == "active")
                )
                meeting = result.scalar_one_or_none()
                if not meeting:
                    logger.info("No active meeting found for bot %s during recovery", bot_id[:8])
                    return None

                # Load agent info
                agent_result = await db.execute(
                    select(Agent).where(Agent.id == meeting.agent_id)
                )
                agent = agent_result.scalar_one_or_none()

                agent_config = {
                    "agent_id": str(meeting.agent_id),
                    "user_id": str(meeting.user_id),
                    "agent_name": agent.name if agent else "Synth",
                    "mode": agent.mode if agent else "general",
                    "persona_id": getattr(agent, "persona_id", "general") if agent else "general",
                    "description": agent.description if agent else "",
                    "voice": agent.voice if agent else "female",
                    "system_prompt": agent.system_prompt if agent else "",
                }

                session = MeetingSession(
                    meeting_id=meeting.meeting_link,
                    agent_config=agent_config,
                )
                session.bot_id = bot_id

                persona_id = resolve_persona_id(
                    agent_config.get("mode", "general"),
                    agent_config.get("persona_id"),
                )
                persisted_prompt = (agent_config.get("system_prompt") or "").strip()
                if persisted_prompt:
                    session.agent_config["system_prompt"] = persisted_prompt
                else:
                    session.agent_config["system_prompt"] = build_prompt_for_mode(
                        agent_config.get("mode", "general"),
                        agent_config.get("description", ""),
                        persona_id,
                    )
                session.agent_config["mode"] = "general"
                session.agent_config["persona_id"] = persona_id
                session.agent_config["voice"] = agent_config.get("voice")

                session.context_manager.rolling_summary.set_llm_client(self._llm_client)

                # Wire up RAG pipeline
                from app.api.routes.documents import _get_rag_pipeline
                rag = _get_rag_pipeline(str(meeting.agent_id))
                session.context_manager.set_rag_pipeline(rag)

                # Load document summaries
                from app.models.database import Document
                doc_result = await db.execute(
                    select(Document).where(
                        Document.agent_id == meeting.agent_id,
                        Document.parsed.is_(True),
                        Document.doc_summary.isnot(None),
                    )
                )
                for doc in doc_result.scalars().all():
                    session.context_manager.add_document_summary(doc.filename, doc.doc_summary)

                # Load past meeting summaries for cross-meeting memory
                try:
                    from sqlalchemy.orm import joinedload
                    past_result = await db.execute(
                        select(Meeting)
                        .options(joinedload(Meeting.summary))
                        .where(
                            Meeting.user_id == meeting.user_id,
                            Meeting.agent_id == meeting.agent_id,
                            Meeting.status == "ended",
                            Meeting.id != meeting.id,
                        )
                        .order_by(Meeting.created_at.desc())
                        .limit(3)
                    )
                    for pm in past_result.unique().scalars().all():
                        if pm.summary and pm.summary.content:
                            date_str = pm.created_at.strftime("%Y-%m-%d %H:%M") if pm.created_at else "unknown"
                            session.context_manager.add_past_meeting_summary(date_str, pm.summary.content)
                except Exception as past_exc:
                    logger.warning("Failed to load past summaries during recovery: %s", past_exc)

                # Restore context checkpoint if available (crash recovery)
                if meeting.context_checkpoint:
                    try:
                        import json
                        checkpoint = json.loads(meeting.context_checkpoint)
                        session.context_manager.restore_from_checkpoint(checkpoint)
                    except Exception as ckpt_exc:
                        logger.warning("Failed to restore context checkpoint: %s", ckpt_exc)

                # Wire up screen capture
                self.wire_screen_capture(session)

                session.transition(SessionState.JOINING)
                session.transition(SessionState.LISTENING)

                self.sessions[session.session_id] = session
                self._sessions_by_bot_id[bot_id] = session.session_id
                self._ensure_session_tracking(session.session_id)

                from app.core.vad import VoiceActivityDetector
                self._vad_instances[session.session_id] = VoiceActivityDetector(
                    sample_rate=16000, threshold=0.5,
                )

                logger.info("Recovered session %s for bot %s (with RAG + docs)", session.session_id, bot_id)
                return session

        except Exception as exc:
            logger.error("Failed to recover session for bot %s: %s", bot_id, exc, exc_info=True)
            return None

    async def process_webhook_transcript(
        self,
        bot_id: str,
        speaker: str,
        text: str,
        sentiment: str = "",
    ) -> None:
        """Process a transcript chunk received via Recall.ai webhook.

        Feeds the transcript into the context manager and checks for wake
        word. If detected, runs the full question-handling pipeline
        (filler → context → LLM → TTS → send audio).

        Args:
            bot_id: The Recall.ai bot ID from the webhook payload.
            speaker: Name of the meeting participant who spoke.
            text: The transcribed text.
            sentiment: Speaker sentiment from Deepgram (positive/negative/neutral).
        """
        session = await self.get_or_recover_session(bot_id)
        if not session:
            logger.warning("No active meeting for bot_id=%s", bot_id)
            return

        if not session.is_active:
            return

        # Safety net: ensure all per-session tracking dicts exist
        self._ensure_session_tracking(session.session_id)

        # Detect stop phrases (module-level _STOP_PHRASES)
        text_lower = text.lower().strip().rstrip(".,!?")
        is_stop = any(phrase in text_lower for phrase in _STOP_PHRASES)

        # If someone speaks while bot is responding, shut up immediately
        if session.get_state() == SessionState.RESPONDING:
            sid = session.session_id
            self._interrupted[sid] = True
            # Tell Recall.ai to stop playing audio right now
            if session.bot_id:
                _task = asyncio.create_task(self._recall_client.stop_audio(session.bot_id))
                _task.add_done_callback(_log_task_exception)
            # Only queue as follow-up question if it's NOT a stop phrase
            if not is_stop:
                self._queued_question[sid] = {
                    "question": text,
                    "speaker": speaker,
                    "timestamp": time.time(),
                }
            logger.info("Participant interrupted bot — stopped audio for session %s", sid[:8])
            return

        # Stop phrase — kill audio AND close follow-up window so bot goes silent
        if is_stop:
            if session.bot_id:
                _task = asyncio.create_task(self._recall_client.stop_audio(session.bot_id))
                _task.add_done_callback(_log_task_exception)
            # Close the follow-up window so bot stops listening for questions
            self._last_response_time.pop(session.session_id, None)
            self._followup_speakers.pop(session.session_id, None)
            self._pending_question.pop(session.session_id, None)
            logger.info("Stop phrase detected — killed audio + follow-up for session %s", session.session_id[:8])
            return

        # Echo prevention: ignore transcripts during cooldown after bot speaks
        last_resp = self._last_response_time.get(session.session_id, 0)
        time_since_response = time.time() - last_resp
        if last_resp > 0 and time_since_response < self._cooldown_seconds:
            return

        # Feed transcript into context manager (always, even if no trigger)
        transcript_line = f"{speaker}: {text}" if speaker else text
        session.context_manager.add_transcript(transcript_line)

        # Background: check for verifiable claims (non-blocking)
        if contains_verifiable_claim(text):
            _task = asyncio.create_task(self._check_insight(session, speaker, text))
            _task.add_done_callback(_log_task_exception)

        # Check for wake word OR follow-up window
        sid = session.session_id
        wake_word = session.agent_config.get("wake_word", "nova")
        wake_detected, question = detect_wake_word(text, wake_word=wake_word)
        is_question = False

        if wake_detected:
            clean = question.strip(" .,!?;:-") if question else ""
            self._last_speaker[sid] = speaker
            self._last_sentiment[sid] = sentiment
            if clean:
                is_question = True
                question = clean
            else:
                # Wake word detected but no question yet (e.g. "Hey Assistant.")
                # Acknowledge immediately so the user knows the bot heard them,
                # then wait for the actual question in the next chunk.
                self._pending_question[sid] = {
                    "question": "",
                    "speaker": speaker,
                    "timestamp": time.time(),
                }
                # Send a quick acknowledgment audio
                if session.bot_id and self._tts:
                    try:
                        ack_phrase = "Yes?"
                        ack_mp3 = self._filler_manager._mp3_cache.get(ack_phrase)
                        if not ack_mp3:
                            # Synthesize and cache a short acknowledgment
                            ack_audio = self._tts.synthesize(ack_phrase)
                            if ack_audio:
                                ack_mp3 = self._recall_client.pcm_to_mp3_b64(ack_audio)
                                self._filler_manager._mp3_cache[ack_phrase] = ack_mp3
                        if ack_mp3:
                            await self._recall_client.send_audio_b64(session.bot_id, ack_mp3)
                            logger.info("Acknowledgment sent for session %s", sid[:8])
                    except Exception as exc:
                        logger.debug("Ack send failed: %s", exc)
                # Open follow-up window so the next speech is captured
                self._last_response_time[sid] = time.time()
                return
        else:
            # Check if this speaker has a pending question waiting for content
            # (wake word was in a previous chunk, question follows now)
            pending = self._pending_question.get(sid)
            if pending and pending["speaker"] == speaker and not pending["question"].strip():
                pending["question"] = text.strip()
                pending["timestamp"] = time.time()
                # Schedule processing after collect time
                _task = asyncio.create_task(self._wait_and_process(session, pending["timestamp"]))
                _task.add_done_callback(_log_task_exception)
                return

            # Follow-up window logic — accept questions without wake word
            # within 10s of the bot's last response
            in_followup = last_resp > 0 and time_since_response < (self._cooldown_seconds + self._followup_window)

            logger.debug(
                "FOLLOWUP CHECK sid=%s speaker=%s in_followup=%s time_since=%0.1fs words=%d last_speaker=%s text=%s",
                sid[:8], speaker, in_followup, time_since_response, len(text.split()),
                self._last_speaker.get(sid, "?"), text[:60],
            )

            if not in_followup or len(text.split()) < 4:
                if not in_followup:
                    self._followup_speakers.pop(sid, None)
                return

            # Skip if the utterance is clearly directed at another participant
            bot_name = session.agent_config.get("agent_name", "Synth")
            wake_word_cfg = session.agent_config.get("wake_word", "nova")
            known_people = frozenset(session.context_manager._entities.get("people", set()))
            if is_directed_at_other(
                text,
                bot_names=(bot_name, wake_word_cfg),
                known_participants=known_people,
            ):
                logger.debug("Follow-up directed at another person, ignoring: %s", text[:60])
                return

            has_marker = has_coherence_marker(text)

            # Semantic check: does this follow-up share topic words with
            # the bot's last response? Catches "tell me more about Delhi"
            # after the bot discussed Delhi restaurants.
            has_topic_overlap = False
            if not has_marker:
                recent_bot = session.context_manager.raw_buffer.get_recent(minutes=1)
                if recent_bot:
                    bot_words = set(w.lower() for w in recent_bot.split() if len(w) > 4)
                    user_words = set(w.lower() for w in text.split() if len(w) > 4)
                    overlap = bot_words & user_words
                    if len(overlap) >= 1:
                        has_topic_overlap = True

            if not has_marker and not has_topic_overlap:
                logger.debug("Dropping incoherent follow-up: %s", text[:60])
                return

            # Accept follow-up from the original speaker or one new speaker
            original = self._last_speaker.get(sid, "")
            speakers_heard = self._followup_speakers.setdefault(sid, set())
            speakers_heard.add(speaker)

            if speaker == original:
                is_question = True
                question = text
            elif len(speakers_heard) <= 2:
                # Allow follow-ups from a second speaker too
                is_question = True
                question = text
            else:
                return

        if not is_question:
            return

        # Buffer the question — wait for user to finish speaking
        pending = self._pending_question.get(sid)
        now = time.time()

        if pending and pending["speaker"] == speaker:
            # Same speaker still talking — append to their question
            pending["question"] = pending["question"] + " " + question
            pending["timestamp"] = now
            return  # wait for more
        elif pending and pending["speaker"] != speaker:
            # Different speaker — process the old pending question first
            await self._process_pending_question(session)

        # Start collecting this question
        self._pending_question[sid] = {
            "question": question,
            "speaker": speaker,
            "timestamp": now,
        }

        if len(question.split()) >= 4:
            _task = asyncio.create_task(self._process_pending_question(session))
            _task.add_done_callback(_log_task_exception)
        else:
            _task = asyncio.create_task(self._wait_and_process(session, now))
            _task.add_done_callback(_log_task_exception)

    async def _wait_and_process(self, session: MeetingSession, trigger_time: float) -> None:
        """Wait for question collection time, then process if no new input arrived."""
        await asyncio.sleep(self._question_collect_time)

        sid = session.session_id
        pending = self._pending_question.get(sid)
        if not pending:
            return
        # If timestamp hasn't changed since trigger, user finished speaking — process now
        if pending["timestamp"] <= trigger_time + 0.1:
            await self._process_pending_question(session)
            return
        # Timestamp was updated (more words arrived) — check if user stopped since then
        if time.time() - pending["timestamp"] >= self._question_collect_time - 0.1:
            await self._process_pending_question(session)

    async def _process_pending_question(self, session: MeetingSession) -> None:
        """Process a fully collected question.

        Acquires the per-session processing lock to prevent concurrent
        question handling for the same session.
        """
        sid = session.session_id
        pending = self._pending_question.pop(sid, None)
        if not pending:
            return

        question = pending["question"].strip()
        speaker = pending["speaker"]
        if not question or len(question.split()) < 2:
            return

        logger.warning("QUESTION session=%s speaker=%s question=%s", sid[:8], speaker, question)

        await self._lazy_load_models()

        lock = self._processing_lock.get(sid)
        if lock is None:
            self._ensure_session_tracking(sid)
            lock = self._processing_lock[sid]

        async with lock:
            await self._handle_question(session, question, speaker=speaker)

    async def _check_insight(self, session: MeetingSession, speaker: str, text: str) -> None:
        """Background task: verify a factual claim and store correction if wrong."""
        sid = session.session_id
        now = time.time()
        last_check = self._insight_last_check.get(sid, 0.0)
        if sid in self._insight_inflight or (now - last_check) < _INSIGHT_CHECK_COOLDOWN_SECONDS:
            logger.debug("Skipping insight check for session %s due to rate limit", sid[:8])
            return

        self._insight_inflight.add(sid)
        self._insight_last_check[sid] = now

        try:
            result = await verify_claim(
                text=text,
                speaker=speaker,
                search_client=self._search_client,
                llm_client=self._llm_client,
            )
            if result:
                session.insights.append(result)
                logger.warning(
                    "INSIGHT STORED session=%s: %s",
                    session.session_id[:8], result["correction"],
                )
        except Exception as exc:
            logger.debug("Insight check failed: %s", exc)
        finally:
            self._insight_inflight.discard(session.session_id)

    async def _handle_question(
        self,
        session: MeetingSession,
        question: str,
        speaker: str = "",
    ) -> bytes | None:
        """Handle a detected question end-to-end.

        Assembles context, optionally searches the web, queries the LLM,
        and synthesizes the response as audio. When *speaker* is provided,
        the filler and LLM response are personalized with their name.

        Args:
            session: The active MeetingSession.
            question: The extracted question text after the wake word.
            speaker: Name of the participant who asked (for personalization).

        Returns:
            Synthesized audio bytes for the response, or ``None`` on error.
        """
        if self._tts is None:
            return None

        try:
            session.transition(SessionState.RESPONDING)
        except ValueError:
            logger.warning("Could not transition to RESPONDING for session %s", session.session_id)
            return None

        try:
            timer = QuestionStageTimer(session.session_id, question)
            from app.utils.query_router import classify_query, needs_web_search
            category = classify_query(question)
            filler_duration = 0.0
            if session.bot_id:
                persona_voice = get_persona_tts_voice(session.agent_config.get("persona_id"))

                # Speaker-personalized filler: "Sure Yash, let me check."
                filler_phrase = self._filler_manager.get_filler_for_category(category)
                if speaker:
                    filler_phrase = self._filler_manager.get_personalized_filler(
                        category, speaker,
                    )

                # Try pre-cached audio first, fall back to live synthesis for personalized fillers
                filler_pcm = b""
                filler_b64 = ""
                if not speaker:
                    filler_pcm = self._filler_manager.get_filler_audio(category, voice=persona_voice)
                    filler_b64 = self._filler_manager.get_filler_mp3_b64(category, voice=persona_voice)

                if not filler_b64 and self._tts:
                    async with self._tts_lock:
                        self._ensure_tts_voice_for_persona(session.agent_config.get("persona_id"))
                        loop = asyncio.get_running_loop()
                        filler_pcm = await loop.run_in_executor(
                            None, self._tts.synthesize, filler_phrase,
                        )
                    if filler_pcm:
                        filler_b64 = self._recall_client.pcm_to_mp3_b64(filler_pcm)

                if filler_b64:
                    await self._recall_client.send_audio_b64(session.bot_id, filler_b64)
                    from app.utils.echo_tracker import record as _echo_record
                    _echo_record(session.bot_id, filler_phrase)
                    if filler_pcm:
                        filler_duration = len(filler_pcm) / 48000
            filler_sent_at = time.time()
            timer.mark("filler_sent")

            # Rewrite the question with recent conversation context so both
            # RAG search and web search include the right topic keywords.
            # e.g. "give me good locations in Delhi" → "give me good locations
            # in Delhi (context: restaurant India opportunities)"
            recent_text = session.context_manager.raw_buffer.get_recent(minutes=5)
            search_query = session.context_manager._rewrite_query(question, recent_text)
            logger.debug("Search query: %s → %s", question, search_query)

            # Assemble context + web search in parallel (search runs speculatively).
            # Search is gated: skip Serper for questions clearly bound to meeting
            # or document context. Defaults to searching otherwise — recall over
            # precision so we never miss a needed lookup.
            context_task = asyncio.get_running_loop().run_in_executor(
                None,
                session.context_manager.assemble_context,
                question,
                session.session_id,
            )
            if needs_web_search(question):
                search_task = asyncio.create_task(
                    self._search_client.search_formatted(search_query)
                )
                t_search_started = time.time()
            else:
                search_task = None
                t_search_started = None
                logger.debug(
                    "Skipping web search for meeting/document question: %s",
                    question[:60],
                )

            context = await context_task
            timer.mark("context_ready")

            if self._should_cancel_output(session):
                if search_task is not None and not search_task.done():
                    search_task.cancel()
                    try:
                        await search_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass
                try:
                    session.transition(SessionState.LISTENING)
                except ValueError:
                    pass
                timer.mark("aborted_session_end")
                timer.log_summary({"aborted": True})
                return None

            if session.operator_instructions:
                recent_instructions = session.operator_instructions[-3:]
                instruction_block = "\n".join(f"- {item}" for item in recent_instructions)
                context = (
                    f"{context}\n\n=== OPERATOR INSTRUCTIONS (HIGHEST PRIORITY) ===\n"
                    f"{instruction_block}\n"
                    "Follow these instructions as long as they do not conflict with safety constraints."
                )
            # Include stored insights/corrections ONLY when the user asks about them.
            if session.insights:
                q_lower = question.lower()
                if any(trigger in q_lower for trigger in _CORRECTION_TRIGGERS):
                    insights_text = "\n".join(
                        f"- {i['speaker']} said: \"{i['claim'][:80]}\" — Correction: {i['correction']}"
                        for i in session.insights
                    )
                    context = f"{context}\n\n=== CORRECTIONS NOTED DURING MEETING ===\n{insights_text}\n(Share these corrections since the user asked about accuracy.)"

            # Add sentiment hint if available (helps LLM match tone)
            mood = self._last_sentiment.get(session.session_id, "")
            if mood and mood in ("positive", "negative", "neutral"):
                context = f"{context}\n\n(Speaker mood: {mood}. Match your tone accordingly.)"

            # Attach search results if the search was actually fired (ran in parallel,
            # adds no latency). Skipped entirely when needs_web_search() returned False.
            if search_task is not None:
                try:
                    search_results = await search_task
                    if search_results and search_results.strip() and "No results found" not in search_results:
                        context = (
                            f"{context}\n\n=== WEB SEARCH RESULTS ===\n"
                            f"{search_results}\n"
                            f"(Include relevant web search info in your answer. Combine it with "
                            f"document and meeting context for a complete response.)"
                        )
                    if t_search_started is not None:
                        logger.debug(
                            "Web search took %.0fms",
                            (time.time() - t_search_started) * 1000,
                        )
                except Exception as exc:
                    logger.debug("Speculative search failed (non-blocking): %s", exc)

            timer.mark("search_phase_done")
            system_prompt = session.agent_config.get("system_prompt", "")
            self._interrupted[session.session_id] = False

            # Wait for filler to finish playing before first sentence
            elapsed = time.time() - filler_sent_at
            remaining = filler_duration - elapsed
            if remaining > 0 and not self._should_cancel_output(session):
                await asyncio.sleep(remaining)
            timer.mark("pre_llm_stream")

            # --- Streaming pipeline: LLM sentence -> TTS -> send audio ---
            # Each sentence is synthesized and sent as soon as it arrives
            # from the LLM, cutting perceived latency by 60-70%.
            response_parts: list[str] = []
            total_playback = 0.0
            playback_started_at: float | None = None
            stream_timed_out = False

            try:
                async with asyncio.timeout(30.0):
                    async for sentence in self._llm_client.async_query_stream(
                        context=context,
                        question=question,
                        system_prompt=system_prompt,
                        speaker=speaker,
                        should_cancel=lambda: self._should_cancel_output(session),
                    ):
                        if self._should_cancel_output(session):
                            logger.info(
                                "Output cancelled — stopping LLM stream for %s",
                                session.session_id[:8],
                            )
                            if session.bot_id:
                                await self._recall_client.stop_audio(session.bot_id)
                            break

                        cleaned = sentence.strip().strip("()[]").lower()
                        if not cleaned or cleaned in ("silence", "silent", "..."):
                            continue

                        response_parts.append(sentence)

                        session_tts = self._get_session_tts(
                            session.session_id,
                            session.agent_config.get("persona_id"),
                        )
                        if session_tts is None:
                            logger.error("No TTS available for session %s", session.session_id[:8])
                            continue
                        for tts_piece in split_text_for_tts(sentence):
                            if self._should_cancel_output(session):
                                break
                            sentence_audio = await self._synthesize_tts_audio(
                                session_tts,
                                tts_piece,
                                session.agent_config.get("persona_id"),
                            )
                            if session.bot_id and sentence_audio:
                                await self._recall_client.send_audio(session.bot_id, sentence_audio)
                                total_playback, playback_started_at = self._enqueue_playback_chunk(
                                    total_playback,
                                    playback_started_at,
                                    sentence_audio,
                                )

            except TimeoutError:
                stream_timed_out = True
                timer.mark("stream_timeout")
                logger.warning("LLM stream timed out after 30s for session %s", session.session_id[:8])
                if not response_parts:
                    fallback = "I'm taking too long to think about that. Could you ask again?"
                    response_parts.append(fallback)
                    session_tts = self._get_session_tts(
                        session.session_id,
                        session.agent_config.get("persona_id"),
                    )
                    if session_tts and session.bot_id:
                        fallback_audio = await self._synthesize_tts_audio(
                            session_tts,
                            fallback,
                            session.agent_config.get("persona_id"),
                        )
                        if fallback_audio:
                            await self._recall_client.send_audio(session.bot_id, fallback_audio)
                            total_playback, playback_started_at = self._enqueue_playback_chunk(
                                total_playback,
                                playback_started_at,
                                fallback_audio,
                            )

            response_text = " ".join(response_parts)

            if not response_text.strip():
                logger.info("LLM returned nothing for session %s — skipping", session.session_id[:8])
                try:
                    session.transition(SessionState.LISTENING)
                except ValueError:
                    pass
                timer.mark("pipeline_done")
                timer.log_summary({"sentences": 0, "empty": True, "stream_timeout": stream_timed_out})
                return None

            # Log interrupted partial responses for context
            if self._interrupted.get(session.session_id, False) and response_parts:
                partial = (
                    f"[Assistant was answering \"{question}\" and said: "
                    f"\"{response_text.strip()}\" before being interrupted]"
                )
                session.context_manager.add_transcript(partial)
                response_text = ""

            if response_text:
                logger.warning(
                    "RESPONSE session=%s (%d chars, streamed): %s",
                    session.session_id[:8],
                    len(response_text),
                    response_text[:100],
                )

                # Wait for remaining playback to finish (interruption check)
                playback_remaining = self._remaining_playback_time(
                    total_playback,
                    playback_started_at,
                )
                while playback_remaining > 0:
                    if self._should_cancel_output(session):
                        logger.info("Interrupted during playback — stopping for session %s", session.session_id[:8])
                        if session.bot_id:
                            await self._recall_client.stop_audio(session.bot_id)
                        break
                    await asyncio.sleep(min(0.3, playback_remaining))
                    playback_remaining = self._remaining_playback_time(
                        total_playback,
                        playback_started_at,
                    )

            if response_text:
                bot_name = session.agent_config.get("agent_name", "Nova")
                session.context_manager.add_transcript(
                    f"{bot_name}: {response_text.strip()}"
                )

            if response_text:
                from app.utils.echo_tracker import record as _echo_record
                _echo_record(session.bot_id, response_text)

            # Reset follow-up speaker tracking for new window
            self._followup_speakers.pop(session.session_id, None)
            was_interrupted = self._interrupted.pop(session.session_id, False)
            session.output_stop_requested = False

            # Transition back to LISTENING
            try:
                session.transition(SessionState.LISTENING)
            except ValueError:
                pass

            # Follow-up window starts now
            self._last_response_time[session.session_id] = time.time()

            # Process queued question only if it contains a wake word
            # (if the person just interrupted to talk normally, don't respond)
            queued = self._queued_question.pop(session.session_id, None)
            if queued:
                wake_word_cfg = session.agent_config.get("wake_word", "nova")
                wake_detected, q = detect_wake_word(queued["question"], wake_word=wake_word_cfg)
                if wake_detected and q:
                    logger.info("Processing queued question for session %s", session.session_id[:8])
                    # Route through _process_pending_question to acquire the processing lock
                    self._pending_question[session.session_id] = {
                        "question": f"{wake_word_cfg} {q}",  # re-add wake word for detection
                        "speaker": queued.get("speaker", ""),
                        "timestamp": time.time(),
                    }
                    _task = asyncio.create_task(self._process_pending_question(session))
                    _task.add_done_callback(_log_task_exception)
                elif was_interrupted:
                    logger.info("Participant interrupted without wake word — staying silent for session %s", session.session_id[:8])

            timer.mark("pipeline_done")
            timer.log_summary(
                {
                    "sentences": len(response_parts),
                    "stream_timeout": stream_timed_out,
                    "session_end": session.session_end_requested,
                    "cancelled": was_interrupted or session.session_end_requested,
                },
            )
            return None  # Audio already sent via streaming

        except Exception as exc:
            logger.error(
                "Error handling question in session %s: %s",
                session.session_id,
                exc,
                exc_info=True,
            )
            # Mute and recover to LISTENING state
            if session.bot_id:
                try:
                    await self._recall_client.mute(session.bot_id)
                except Exception as mute_exc:
                    logger.warning("Failed to mute during error recovery: %s", mute_exc)
            try:
                session.transition(SessionState.LISTENING)
            except ValueError:
                pass
            return None

    # ------------------------------------------------------------------
    # Cross-meeting memory
    # ------------------------------------------------------------------

    async def _save_meeting_summary(
        self,
        bot_id: str,
        content: str,
        entities: dict[str, set[str]] | None = None,
    ) -> None:
        """Persist meeting summary and structured entities to the database.

        Saves both the prose summary (for cross-meeting context) and
        structured entities (decisions, action items, people) as first-class
        fields for production reuse (Item 5).

        Args:
            bot_id: The Recall.ai bot ID to look up the meeting record.
            content: The rolling summary content to save.
            entities: Optional dict of entity sets from the context manager.
        """
        try:
            import json
            from app.models.database import Meeting, MeetingSummary, AsyncSessionLocal
            from sqlalchemy import select

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Meeting).where(Meeting.bot_id == bot_id)
                )
                meeting = result.scalar_one_or_none()
                if not meeting:
                    logger.warning("No meeting found for bot %s — summary not saved", bot_id[:8])
                    return

                existing = await db.execute(
                    select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
                )
                if existing.scalar_one_or_none():
                    logger.debug("Summary already exists for meeting %s", meeting.id)
                    return

                # Build structured fields from entity tracker
                key_points: list[str] = []
                action_items: list[str] = []
                decisions: list[str] = []
                if entities:
                    decisions = sorted(entities.get("decisions", set()))
                    action_items = sorted(entities.get("action_items", set()))
                    people = sorted(entities.get("people", set()))
                    if people:
                        key_points.append(f"Participants: {', '.join(people)}")

                summary_record = MeetingSummary(
                    meeting_id=meeting.id,
                    content=content,
                    key_points=json.dumps(key_points) if key_points else None,
                    action_items=json.dumps(action_items) if action_items else None,
                    decisions=json.dumps(decisions) if decisions else None,
                )
                db.add(summary_record)
                await db.commit()
                logger.info("Meeting summary saved for meeting %s (bot %s)", meeting.id, bot_id[:8])
        except Exception as exc:
            logger.error("Failed to save meeting summary: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self, session_id: str) -> MeetingSession:
        """Look up a session by ID or raise.

        Args:
            session_id: The session ID to look up.

        Returns:
            The MeetingSession instance.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id!r} not found")
        return session

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully shut down the bot engine.

        Stops all active sessions and closes shared clients.
        """
        active_ids = [
            sid for sid, s in self.sessions.items() if s.is_active
        ]

        for session_id in active_ids:
            try:
                await self.stop_meeting(session_id)
            except Exception as exc:
                logger.error("Error stopping session %s during shutdown: %s", session_id, exc)

        await self._recall_client.close()
        await self._search_client.close()
        logger.info("BotEngine shut down")
