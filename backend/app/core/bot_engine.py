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

import numpy as np

from app.config import get_settings
from app.context.manager import ContextManager
from app.core.llm import LLMClient
from app.core.search import SearchClient
from app.core.vision import VisionProcessor
from app.meeting.recall_client import RecallClient, RecallClientError
from app.meeting.session import MeetingSession, SessionState
from app.utils.bot_profiles import get_persona_tts_voice
from app.utils.filler import FillerManager
from app.utils.prompt_builder import build_prompt_for_mode, resolve_persona_id
from app.core.insight_detector import contains_verifiable_claim, verify_claim
from app.utils.wake_word import detect as detect_wake_word

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
        self._question_collect_time: float = 0.5  # seconds to wait for user to finish speaking
        self._followup_window: float = 8.0  # seconds after audio finishes playing to accept follow-ups
        self._cooldown_seconds: float = 0.0  # no cooldown
        self._processing_lock: dict[str, asyncio.Lock] = {}  # session_id -> lock
        self._tts_lock: asyncio.Lock = asyncio.Lock()  # serializes TTS voice switch + synthesis across sessions

        # Lightweight services — safe to initialize at startup
        self._settings = get_settings()
        self._recall_client: RecallClient = RecallClient()
        self._llm_client: LLMClient = LLMClient()
        self._search_client: SearchClient = SearchClient()
        self._vision_processor: VisionProcessor = VisionProcessor()
        self._filler_manager: FillerManager = FillerManager()

        # Heavy model references — populated by _lazy_load_models()
        self._stt: Any | None = None
        self._tts: Any | None = None
        self._models_loaded: bool = False
        self._model_init_lock: asyncio.Lock = asyncio.Lock()

        # Per-session VAD instances (Silero VAD is stateful, cannot be shared)
        self._vad_instances: dict[str, Any] = {}

        # Per-session audio accumulators: session_id -> list of np arrays
        self._audio_buffers: dict[str, list[np.ndarray]] = {}

        # Per-session sentiment tracking
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
            self._audio_buffers[session.session_id] = []
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

        # Collect transcript data before flushing
        full_transcript = session.context_manager.raw_buffer.get_full_text()
        summary = session.context_manager.rolling_summary.get_summary()

        # Flush remaining transcript chunks to RAG then cleanup
        session.context_manager.flush_remaining_embeddings()

        # Save meeting summary to database for cross-meeting memory
        if session.bot_id and summary:
            _task = asyncio.create_task(self._save_meeting_summary(session.bot_id, summary))
            _task.add_done_callback(_log_task_exception)

        # Clean up all session resources
        vad = self._vad_instances.pop(session_id, None)
        if vad is not None:
            vad.reset()
        self.sessions.pop(session_id, None)
        self._audio_buffers.pop(session_id, None)
        self._last_response_time.pop(session_id, None)
        self._last_speaker.pop(session_id, None)
        self._followup_speakers.pop(session_id, None)
        self._pending_question.pop(session_id, None)
        self._queued_question.pop(session_id, None)
        self._interrupted.pop(session_id, None)
        self._processing_lock.pop(session_id, None)
        self._last_sentiment.pop(session_id, None)
        if session.bot_id:
            self._sessions_by_bot_id.pop(session.bot_id, None)

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

    # ------------------------------------------------------------------
    # Audio processing pipeline
    # ------------------------------------------------------------------

    async def process_audio_chunk(
        self,
        session_id: str,
        audio_chunk: np.ndarray,
    ) -> bytes | None:
        """Process an incoming audio chunk through the full pipeline.

        Pipeline stages:
        1. VAD — detect whether speech is present
        2. If speech detected, accumulate audio frames
        3. When speech ends, transcribe accumulated audio via STT
        4. Check transcript for wake word
        5. If wake word found:
           a. Assemble context from transcript + RAG + documents
           b. Optionally augment with web search results
           c. Send filler audio for latency masking
           d. Query LLM for response
           e. Synthesize response via TTS
           f. Return audio bytes to send into the meeting

        Args:
            session_id: The active session ID.
            audio_chunk: Raw audio samples as a numpy array
                (float32, mono, 16kHz). Expected frame size is 512 samples.

        Returns:
            Audio response bytes (PCM) if the bot should speak,
            or ``None`` if no response is needed for this chunk.

        Raises:
            SessionNotFoundError: If session_id is not found.
        """
        session = self._get_session(session_id)

        if not session.is_active:
            return None

        if self._stt is None or self._tts is None:
            logger.error("Models not loaded — cannot process audio")
            return None

        vad = self._vad_instances.get(session_id)
        if vad is None:
            logger.error("No VAD instance for session %s", session_id)
            return None

        buffer = self._audio_buffers.get(session_id, [])

        # Step 1: Run VAD on the audio frame
        speech_detected = vad.process_audio_frame(audio_chunk)

        if speech_detected:
            # Step 2: Accumulate speech frames
            buffer.append(audio_chunk)
            self._audio_buffers[session_id] = buffer
            return None

        # Speech not detected — check if we just finished a speech segment
        if not buffer:
            # No accumulated speech — nothing to process
            return None

        # Step 3: Speech ended — transcribe the accumulated audio
        speech_audio = np.concatenate(buffer)
        self._audio_buffers[session_id] = []  # Reset buffer

        # Minimum audio length check (ignore very short segments < 0.3s)
        min_samples = int(0.15 * 16000)
        if len(speech_audio) < min_samples:
            return None

        segment = self._stt.transcribe(speech_audio)
        transcript_text = segment.text.strip()

        if not transcript_text:
            return None

        # Feed transcript into the context manager with speaker label
        labeled = f"Participant: {transcript_text}"
        session.context_manager.add_transcript(labeled)

        logger.debug(
            "Session %s transcribed: %s (confidence=%.2f)",
            session_id,
            transcript_text[:80],
            segment.confidence,
        )

        # Step 4: Check for wake word (configurable per agent)
        wake_word = session.agent_config.get("wake_word", "nova")
        wake_detected, question = detect_wake_word(transcript_text, wake_word=wake_word)
        if not wake_detected or not question:
            return None

        if session.operator_muted:
            logger.info(
                "Wake word ignored due to operator mute for session %s",
                session.session_id[:8],
            )
            return None

        logger.warning("WAKE WORD DETECTED session=%s question=%s", session_id, question)

        # Step 5: Process the question
        return await self._handle_question(session, question)

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
                    return None

                # Load agent info
                agent_result = await db.execute(
                    select(Agent).where(Agent.id == meeting.agent_id)
                )
                agent = agent_result.scalar_one_or_none()

                agent_config = {
                    "agent_id": str(meeting.agent_id),
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

                session.transition(SessionState.JOINING)
                session.transition(SessionState.LISTENING)

                self.sessions[session.session_id] = session
                self._sessions_by_bot_id[bot_id] = session.session_id
                self._audio_buffers[session.session_id] = []
                self._ensure_session_tracking(session.session_id)

                from app.core.vad import VoiceActivityDetector
                self._vad_instances[session.session_id] = VoiceActivityDetector(
                    sample_rate=16000, threshold=0.5,
                )

                logger.warning("Recovered session %s for bot %s (with RAG + docs)", session.session_id, bot_id)
                return session

        except Exception as exc:
            logger.error("Failed to recover session for bot %s: %s", bot_id, exc)
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
        session_id = self._sessions_by_bot_id.get(bot_id)
        session = self.sessions.get(session_id) if session_id else None

        # Recover session from DB if not in memory (e.g. after restart)
        if not session:
            session = await self._recover_session(bot_id)
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

        # Stop phrase while audio is still playing (follow-up window)
        if is_stop and session.bot_id:
            _task = asyncio.create_task(self._recall_client.stop_audio(session.bot_id))
            _task.add_done_callback(_log_task_exception)
            logger.info("Stop phrase detected — killed audio for session %s", session.session_id[:8])
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

            # Reject incoherent fragments — follow-ups must look like real sentences
            # (contain a verb, question word, or common conversational pattern)
            text_lower = text.lower().strip()
            _COHERENCE_MARKERS = (
                "what", "who", "where", "when", "why", "how",
                "can", "could", "would", "should", "will", "do", "does", "did",
                "is", "are", "was", "were", "have", "has",
                "tell", "explain", "show", "give", "find", "search",
                "yes", "no", "yeah", "okay", "sure",
                "thank", "stop", "enough",
                "about", "think", "know", "remember", "mean",
                "?",
            )
            if not any(marker in text_lower for marker in _COHERENCE_MARKERS):
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

        # If the question is already substantial (4+ words), process immediately
        # instead of waiting for collect time — feels much more responsive
        if len(question.split()) >= 4:
            _task = asyncio.create_task(self._process_pending_question(session))
            _task.add_done_callback(_log_task_exception)
        else:
            # Short question — wait for more words
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

        # Load TTS lazily if not loaded (use centralized init)
        await self._lazy_load_models()

        # Acquire the per-session lock to serialize question processing
        lock = self._processing_lock.get(sid)
        if lock is None:
            self._ensure_session_tracking(sid)
            lock = self._processing_lock[sid]

        async with lock:
            await self._handle_question(session, question)

    async def _check_insight(self, session: MeetingSession, speaker: str, text: str) -> None:
        """Background task: verify a factual claim and store correction if wrong."""
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

    async def _handle_question(
        self,
        session: MeetingSession,
        question: str,
    ) -> bytes | None:
        """Handle a detected question end-to-end.

        Assembles context, optionally searches the web, queries the LLM,
        and synthesizes the response as audio.

        Args:
            session: The active MeetingSession.
            question: The extracted question text after the wake word.

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
            # Classify question and send context-aware filler immediately
            from app.utils.query_router import classify_query
            category = classify_query(question)
            filler_duration = 0.0
            if session.bot_id:
                filler_phrase = self._filler_manager.get_filler_for_category(category)
                filler_pcm = self._filler_manager._cache.get(filler_phrase, b"")
                filler_b64 = self._filler_manager._mp3_cache.get(filler_phrase, "")
                if filler_b64:
                    await self._recall_client.send_audio_b64(session.bot_id, filler_b64)
                    # Track filler for echo detection
                    from app.api.routes.webhook import _recent_bot_output
                    _recent_bot_output.setdefault(session.bot_id, []).append(filler_phrase.lower())
                    # Calculate filler duration (PCM int16 @ 24kHz = 48000 bytes/sec)
                    if filler_pcm:
                        filler_duration = len(filler_pcm) / 48000
            filler_sent_at = time.time()

            # Assemble context + web search in parallel (search runs speculatively)
            context_task = asyncio.get_running_loop().run_in_executor(
                None,
                session.context_manager.assemble_context,
                question,
                session.session_id,
            )
            search_task = asyncio.create_task(
                self._search_client.search_formatted(question)
            )

            context = await context_task

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

            # Attach search results if available (ran in parallel, adds no latency)
            try:
                search_results = await search_task
                if search_results and search_results.strip():
                    context = (
                        f"{context}\n\n=== WEB SEARCH RESULTS (use only if relevant to the question) ===\n"
                        f"{search_results}"
                    )
            except Exception as exc:
                logger.debug("Speculative search failed (non-blocking): %s", exc)

            # Single LLM call with full context + search results
            system_prompt = session.agent_config.get("system_prompt", "")
            self._interrupted[session.session_id] = False

            response_text = await self._llm_client.async_query(
                context=context,
                question=question,
                system_prompt=system_prompt,
            )

            # Skip non-answers
            cleaned = response_text.strip().strip("()[]").lower()
            if not cleaned or cleaned in ("silence", "silent", "..."):
                logger.info("LLM returned silence for session %s — skipping TTS", session.session_id[:8])
                try:
                    session.transition(SessionState.LISTENING)
                except ValueError:
                    pass
                return None

            # Check if interrupted while LLM was generating
            if self._interrupted.get(session.session_id, False):
                logger.info("Bot interrupted during LLM — going silent for session %s", session.session_id[:8])
                partial = (
                    f"[Assistant was answering \"{question}\" and said: "
                    f"\"{response_text.strip()}\" before being interrupted]"
                )
                session.context_manager.add_transcript(partial)
                response_text = ""

            if response_text:
                logger.warning(
                    "RESPONSE session=%s (%d chars): %s",
                    session.session_id,
                    len(response_text),
                    response_text[:100],
                )

                # Synthesize — hold TTS lock to prevent voice switch races across sessions
                async with self._tts_lock:
                    self._ensure_tts_voice_for_persona(session.agent_config.get("persona_id"))
                    response_audio = self._tts.synthesize(response_text)
                if session.bot_id and response_audio:
                    # Wait for filler to finish playing
                    elapsed = time.time() - filler_sent_at
                    remaining = filler_duration - elapsed
                    if remaining > 0:
                        await asyncio.sleep(remaining)
                    await self._recall_client.send_audio(session.bot_id, response_audio)
                    logger.warning("Audio sent to bot %s", session.bot_id[:8])

                    # Stay in RESPONDING during playback so interruptions work.
                    # PCM int16 at 24kHz = 48000 bytes per second.
                    playback_duration = (
                        len(response_audio) / (24000 * 2)
                        if response_audio
                        else len(response_text) / 15
                    )
                    playback_start = time.time()

                    # Poll for interruption during playback
                    while time.time() - playback_start < playback_duration:
                        if self._interrupted.get(session.session_id, False):
                            logger.info("Interrupted during playback — stopping audio for session %s", session.session_id[:8])
                            await self._recall_client.stop_audio(session.bot_id)
                            partial = (
                                f"[Assistant was answering \"{question}\" and said: "
                                f"\"{response_text.strip()}\" before being interrupted]"
                            )
                            session.context_manager.add_transcript(partial)
                            break
                        await asyncio.sleep(0.3)  # check every 300ms

            # Track response text for echo detection
            if response_text:
                from app.api.routes.webhook import _recent_bot_output
                echoes = _recent_bot_output.setdefault(session.bot_id, [])
                echoes.append(response_text.lower())
                if len(echoes) > 5:
                    _recent_bot_output[session.bot_id] = echoes[-5:]

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
                        "question": f"nova {q}",  # re-add wake word for detection
                        "speaker": queued.get("speaker", ""),
                        "timestamp": time.time(),
                    }
                    _task = asyncio.create_task(self._process_pending_question(session))
                    _task.add_done_callback(_log_task_exception)
                elif was_interrupted:
                    logger.info("Participant interrupted without wake word — staying silent for session %s", session.session_id[:8])

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
                except Exception:
                    pass
            try:
                session.transition(SessionState.LISTENING)
            except ValueError:
                pass
            return None

    # ------------------------------------------------------------------
    # Cross-meeting memory
    # ------------------------------------------------------------------

    async def _save_meeting_summary(self, bot_id: str, content: str) -> None:
        """Persist meeting summary to the database for cross-meeting memory.

        Args:
            bot_id: The Recall.ai bot ID to look up the meeting record.
            content: The rolling summary content to save.
        """
        try:
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

                # Check if summary already exists
                existing = await db.execute(
                    select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
                )
                if existing.scalar_one_or_none():
                    logger.debug("Summary already exists for meeting %s", meeting.id)
                    return

                summary_record = MeetingSummary(
                    meeting_id=meeting.id,
                    content=content,
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
