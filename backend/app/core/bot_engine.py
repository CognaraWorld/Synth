"""Main bot orchestrator engine.

Central coordinator that ties together all subsystems: VAD, STT, TTS,
LLM, context management, and the Recall.ai meeting client. Manages
the full lifecycle of a bot session from joining to leaving a meeting.

Phase 6 implementation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

from app.config import get_settings
from app.context.manager import ContextManager
from app.core.llm import LLMClient
from app.core.search import SearchClient
from app.core.vision import VisionProcessor
from app.meeting.recall_client import RecallClient, RecallClientError
from app.meeting.session import MeetingSession, SessionState
from app.utils.filler import FillerManager
from app.utils.prompt_builder import build_custom_prompt, build_general_prompt
from app.utils.query_router import needs_web_search
from app.utils.wake_word import detect as detect_wake_word

logger = logging.getLogger(__name__)


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

        # Lightweight services — safe to initialize at startup
        self._settings = get_settings()
        self._recall_client: RecallClient = RecallClient()
        self._llm_client: LLMClient = LLMClient()
        self._search_client: SearchClient = SearchClient()
        self._vision_processor: VisionProcessor = VisionProcessor()
        self._filler_manager: FillerManager = FillerManager()

        # Heavy model references — populated by _lazy_load_models()
        self._vad: Any | None = None
        self._stt: Any | None = None
        self._tts: Any | None = None
        self._models_loaded: bool = False

        # Per-session audio accumulators: session_id -> list of np arrays
        self._audio_buffers: dict[str, list[np.ndarray]] = {}

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _lazy_load_models(self) -> None:
        """Initialize VAD, STT, and TTS models on first use.

        Called once before the first meeting join. Loads the Silero VAD,
        faster-whisper STT, and Kokoro TTS models into memory.
        """
        if self._models_loaded:
            return

        logger.info("Loading audio processing models (first use)...")

        from app.core.stt import SpeechToText
        from app.core.tts import TextToSpeech
        from app.core.vad import VoiceActivityDetector

        self._vad = VoiceActivityDetector(sample_rate=16000, threshold=0.5)
        self._stt = SpeechToText(model_size="large-v3", language="en", device="cpu")
        self._tts = TextToSpeech(voice="af_heart", sample_rate=24000, speed=1.0)

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
        self._lazy_load_models()

        # Build session
        meeting_id = meeting_link  # Use the link as the meeting identifier
        session = MeetingSession(meeting_id=meeting_id, agent_config=agent_config)

        # Build the system prompt based on agent mode
        mode = agent_config.get("mode", "general")
        if mode == "custom" and "description" in agent_config:
            system_prompt = build_custom_prompt(agent_config["description"])
        else:
            system_prompt = build_general_prompt()
        session.agent_config["system_prompt"] = system_prompt

        # Wire up the rolling summary with the LLM client
        session.context_manager.rolling_summary.set_llm_client(self._llm_client)

        # Wire up the RAG pipeline and load document summaries for this agent
        agent_id = agent_config.get("agent_id")
        if agent_id:
            from app.api.routes.documents import _get_rag_pipeline
            rag = _get_rag_pipeline(str(agent_id))
            session.context_manager.set_rag_pipeline(rag)

            # Load document summaries from DB into context manager
            doc_summaries = agent_config.get("document_summaries", [])
            for doc in doc_summaries:
                session.context_manager.add_document_summary(
                    doc["filename"], doc["summary"]
                )

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

            # Store the session
            self.sessions[session.session_id] = session
            self._audio_buffers[session.session_id] = []

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

        # Collect transcript data
        full_transcript = session.context_manager.raw_buffer.get_full_text()
        summary = session.context_manager.rolling_summary.get_summary()

        # Clean up audio buffer
        self._audio_buffers.pop(session_id, None)

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

        if self._vad is None or self._stt is None or self._tts is None:
            logger.error("Models not loaded — cannot process audio")
            return None

        buffer = self._audio_buffers.get(session_id, [])

        # Step 1: Run VAD on the audio frame
        speech_detected = self._vad.process_audio_frame(audio_chunk)

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
        min_samples = int(0.3 * 16000)
        if len(speech_audio) < min_samples:
            return None

        segment = self._stt.transcribe(speech_audio)
        transcript_text = segment.text.strip()

        if not transcript_text:
            return None

        # Feed transcript into the context manager
        session.context_manager.add_transcript(transcript_text)

        logger.debug(
            "Session %s transcribed: %s (confidence=%.2f)",
            session_id,
            transcript_text[:80],
            segment.confidence,
        )

        # Step 4: Check for wake word
        wake_detected, question = detect_wake_word(transcript_text)
        if not wake_detected or not question:
            return None

        logger.info("Session %s wake word detected, question: %s", session_id, question)

        # Step 5: Process the question
        return await self._handle_question(session, question)

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
            # Transition to RESPONDING
            session.transition(SessionState.RESPONDING)
        except ValueError:
            logger.warning("Could not transition to RESPONDING for session %s", session.session_id)

        try:
            # Send filler audio to mask latency
            if session.bot_id:
                filler_audio = self._filler_manager.get_random_filler_audio()
                await self._recall_client.send_audio(session.bot_id, filler_audio)

            # Raise hand as a visual indicator
            if session.bot_id:
                await self._recall_client.raise_hand(session.bot_id)

            # Assemble context
            context = session.context_manager.assemble_context(
                question=question,
                session_id=session.session_id,
            )

            # Check if web search is needed and augment context
            if needs_web_search(question):
                search_results = await self._search_client.search_formatted(question)
                context = f"{context}\n\n=== WEB SEARCH RESULTS ===\n{search_results}"

            # Query the LLM
            system_prompt = session.agent_config.get("system_prompt", "")
            response_text = await self._llm_client.async_query(
                context=context,
                question=question,
                system_prompt=system_prompt,
            )

            logger.info(
                "Session %s LLM response (%d chars): %s",
                session.session_id,
                len(response_text),
                response_text[:100],
            )

            # Synthesize response to audio
            response_audio = self._tts.synthesize(response_text)

            # Send the response audio into the meeting
            if session.bot_id and response_audio:
                await self._recall_client.send_audio(session.bot_id, response_audio)

            # Transition back to LISTENING
            try:
                session.transition(SessionState.LISTENING)
            except ValueError:
                pass

            return response_audio

        except Exception as exc:
            logger.error(
                "Error handling question in session %s: %s",
                session.session_id,
                exc,
                exc_info=True,
            )
            # Try to recover to LISTENING state
            try:
                session.transition(SessionState.LISTENING)
            except ValueError:
                pass
            return None

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
