"""Recall.ai webhook endpoint.

Receives real-time transcription and bot status events from Recall.ai.
Returns 200 immediately and processes events in background tasks
to avoid webhook timeouts.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import Meeting, AsyncSessionLocal
from app.utils.bot_profiles import get_persona_tts_voice

logger = logging.getLogger(__name__)

# Bounded concurrency: limit parallel webhook processing to prevent
# resource exhaustion under burst traffic (OWASP A05:2021 - Security Misconfiguration)
_webhook_semaphore = asyncio.Semaphore(20)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Singleton BotEngine — initialized on first webhook hit
_bot_engine = None
_greeted_bots: set[str] = set()  # bot_ids that have already been greeted
_recent_bot_output: dict[str, list[str]] = {}  # bot_id -> recent bot output texts for echo detection

# Shared HTTP client for fetching screenshot URLs — avoids per-request connection pool churn
_http_client: "httpx.AsyncClient | None" = None


def _get_http_client() -> "httpx.AsyncClient":
    global _http_client
    if _http_client is None:
        import httpx
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


def get_bot_engine():
    """Get or create the shared BotEngine instance."""
    global _bot_engine
    if _bot_engine is None:
        from app.core.bot_engine import BotEngine
        _bot_engine = BotEngine()
    return _bot_engine


def set_bot_engine(engine):
    """Set the shared BotEngine (called from meetings route)."""
    global _bot_engine
    _bot_engine = engine


def cleanup_bot_tracking(bot_id: str) -> None:
    """Remove per-bot tracking data when a meeting ends.

    Prevents unbounded growth of in-memory sets/dicts over time.
    Called from _handle_status_change on terminal bot states.
    """
    _greeted_bots.discard(bot_id)
    _recent_bot_output.pop(bot_id, None)


@router.post("/recall")
async def recall_webhook(request: Request):
    """Receive events from Recall.ai.

    Returns 200 immediately. Processing happens in a background task
    to keep webhook response time under Recall.ai's timeout.

    Security: validates X-Webhook-Secret header when webhook_secret is
    configured (OWASP A01:2021 - Broken Access Control).
    """
    # Authenticate webhook requests via shared secret header
    settings = get_settings()
    if settings.webhook_secret:
        token = request.headers.get("X-Webhook-Secret", "")
        import hmac
        if not hmac.compare_digest(token, settings.webhook_secret):
            return JSONResponse(
                status_code=401, content={"error": "unauthorized"}
            )

    try:
        payload = await request.json()
    except Exception:
        logger.warning("Invalid JSON in webhook payload")
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "invalid payload"},
        )

    # Log raw payload at debug level only
    logger.debug("WEBHOOK RAW: %s", json.dumps(payload, default=str)[:2000])

    event = payload.get("event", "")
    data = payload.get("data", {})

    # Route to the correct handler — only one task per webhook.
    # Uses bounded concurrency to prevent resource exhaustion.
    handled = False
    if event:
        if event in ("transcript.data", "transcript.partial_data"):
            _task = asyncio.create_task(_bounded_handle_transcription(data))
            _task.add_done_callback(
                lambda t: logger.error("Webhook transcript task failed: %s", t.exception())
                if not t.cancelled() and t.exception()
                else None
            )
            handled = True
        elif event.startswith("bot.") and "status" not in event:
            # bot.joining_call, bot.in_call_recording, bot.call_ended, etc.
            asyncio.create_task(_handle_status_change(data))
            handled = True
        elif "status" in event.lower():
            _task = asyncio.create_task(_bounded_handle_status_change(data))
            _task.add_done_callback(lambda t: logger.error("Webhook status task failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)
            handled = True
        elif event == "video_separate_png.data":
            asyncio.create_task(_handle_video_frame(data))
            handled = True
        elif event in ("participant_events.screenshare_on", "participant_events.screenshare_off"):
            asyncio.create_task(_handle_screenshare_event(event, data))
            handled = True

    if not handled and not event:
        # No event field — direct transcript webhook
        if "bot_id" in payload or "words" in payload or "text" in payload:
            _task = asyncio.create_task(_bounded_handle_transcription(payload))
            _task.add_done_callback(lambda t: logger.error("Webhook task failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)

    return {"status": "ok"}


async def _bounded_handle_transcription(data: dict) -> None:
    """Wrap _handle_transcription with concurrency limit."""
    async with _webhook_semaphore:
        await _handle_transcription(data)


async def _bounded_handle_status_change(data: dict) -> None:
    """Wrap _handle_status_change with concurrency limit."""
    async with _webhook_semaphore:
        await _handle_status_change(data)


async def _handle_transcription(data: dict) -> None:
    """Process a real-time transcription event in the background."""
    try:
        # Extract bot_id: data.bot.id
        bot_id = ""
        bot_obj = data.get("bot", {})
        if isinstance(bot_obj, dict):
            bot_id = bot_obj.get("id", "")
        if not bot_id:
            bot_id = data.get("bot_id", "")

        # Extract speaker and text from data.data structure
        inner_data = data.get("data", {})
        speaker = ""
        text = ""
        is_final = True
        sentiment = ""

        if isinstance(inner_data, dict):
            # Skip interim (partial) results — only process final transcripts
            # Interim results are useful for UI but cause duplicate processing
            is_final = inner_data.get("is_final", True)
            if not is_final:
                return

            # Speaker from participant
            participant = inner_data.get("participant", {})
            if isinstance(participant, dict):
                speaker = participant.get("name", "")

            # Prefer utterance text (complete sentence) over raw words
            utterance_text = inner_data.get("transcript", "")
            if utterance_text:
                text = utterance_text
            else:
                # Fallback to words array
                words = inner_data.get("words", [])
                if words and isinstance(words, list):
                    text = " ".join(
                        w.get("text", "") for w in words if isinstance(w, dict)
                    )

            # Extract sentiment if available (from Deepgram)
            sentiment = inner_data.get("sentiment", "")
            if isinstance(sentiment, dict):
                sentiment = sentiment.get("average", "")

        # Fallback: check top-level fields
        if not text:
            text = data.get("text", "")

        if not text or not text.strip():
            return

        text = text.strip()

        # Filter out the bot's own speech and unresolved speakers.
        # Recall.ai transcribes the bot's own audio as speaker="Unknown" or ""
        # with garbled text, causing echo loops. Real participants always have
        # their names resolved by the meeting platform.
        speaker_lower = speaker.lower().strip()
        if speaker_lower in ("unknown", "", "bot"):
            logger.debug("Ignoring unresolved/bot speaker: %s: %s", speaker, text[:80])
            return
        engine = get_bot_engine()
        _sid = engine._sessions_by_bot_id.get(bot_id)
        _sess = engine.sessions.get(_sid) if _sid else None
        bot_display_name = "synth"
        if _sess:
            bot_display_name = _sess.agent_config.get("agent_name", "synth").lower()
        if speaker_lower == bot_display_name:
            logger.debug("Ignoring bot's own transcript: %s", text[:80])
            return

        # Text-based echo detection: check if this transcript matches recent bot output
        # (Deepgram sometimes attributes bot speech to a real participant)
        if bot_id and bot_id in _recent_bot_output:
            recent_outputs = _recent_bot_output[bot_id]
            text_lower = text.lower().strip()
            for bot_text in recent_outputs:
                bot_lower = bot_text.lower().strip()
                # Check if the transcript is a substring of bot output or vice versa
                if len(text_lower) > 10 and (text_lower in bot_lower or bot_lower in text_lower):
                    logger.debug("Echo detected (text match): %s", text[:80])
                    return
                # Check word overlap — if >60% of words match, it's likely echo
                if len(text_lower.split()) >= 3:
                    text_words = set(text_lower.split())
                    bot_words = set(bot_lower.split())
                    overlap = len(text_words & bot_words)
                    if overlap / len(text_words) > 0.6:
                        logger.debug("Echo detected (word overlap %.0f%%): %s",
                                    overlap / len(text_words) * 100, text[:80])
                        return

        # Quality filter: reject very short fragments that are likely noise
        # But always allow wake word phrases through
        words = text.split()
        if len(words) < 3:
            text_lower = text.lower().strip(" .,!?")
            common_short = {"yes", "no", "yeah", "okay", "ok", "sure", "right",
                           "thanks", "thank you", "stop", "enough", "got it"}
            wake_words = {"nova", "hey nova", "nora", "hey nora", "noah", "hey noah"}
            if text_lower not in common_short and text_lower not in wake_words:
                logger.debug("Dropping short fragment: %s: %s", speaker, text)
                return

        logger.info("TRANSCRIPT [%s] %s: %s", bot_id[:8] if bot_id else "?", speaker, text[:120])

        # Fallback greeting: if status webhook didn't fire, greet on first transcript
        if bot_id and bot_id not in _greeted_bots:
            _greeted_bots.add(bot_id)
            await _send_greeting(bot_id)

        await engine.process_webhook_transcript(bot_id, speaker, text, sentiment=sentiment)

    except Exception as exc:
        logger.error("Error processing transcription webhook: %s", exc, exc_info=True)


async def _handle_status_change(data: dict) -> None:
    """Process a bot status change event."""
    try:
        bot_id = ""
        bot_obj = data.get("bot", {})
        if isinstance(bot_obj, dict):
            bot_id = bot_obj.get("id", "")
        if not bot_id:
            bot_id = data.get("bot_id", "")

        status = data.get("status", {})
        code = status.get("code", "") if isinstance(status, dict) else str(status)

        logger.info("Bot %s status: %s", bot_id[:8], code)

        # Greet immediately when bot joins the call (before anyone speaks)
        if code in ("in_call_recording", "in_call_not_recording"):
            if bot_id and bot_id not in _greeted_bots:
                _greeted_bots.add(bot_id)
                await _send_greeting(bot_id)

        # Map Recall.ai status codes to our meeting status
        status_map = {
            "in_call_recording": "active",
            "in_call_not_recording": "active",
            "call_ended": "ended",
            "done": "ended",
            "fatal": "failed",
            "analysis_done": "ended",
        }

        new_status = status_map.get(code)
        if not new_status:
            return

        # Clean up in-memory tracking for terminal states to prevent
        # unbounded memory growth over long-running server lifetimes
        if new_status in ("ended", "failed") and bot_id:
            cleanup_bot_tracking(bot_id)

        # Update meeting status in database
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Meeting).where(Meeting.bot_id == bot_id)
            )
            meeting = result.scalar_one_or_none()
            if meeting and meeting.status != new_status:
                meeting.status = new_status
                await db.commit()
                logger.info(
                    "Meeting %s status updated to %s (bot %s)",
                    meeting.id, new_status, bot_id[:8],
                )

    except Exception as exc:
        logger.error("Error processing status webhook: %s", exc, exc_info=True)


async def _handle_video_frame(data: dict) -> None:
    """Process a video_separate_png.data event from Recall.ai.

    Filters for screenshare-type frames only, then delegates to
    ScreenCaptureManager for change detection and Gemini extraction.
    """
    try:
        bot_id = ""
        bot_obj = data.get("bot", {})
        if isinstance(bot_obj, dict):
            bot_id = bot_obj.get("id", "")
        if not bot_id:
            return

        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return

        # Only process screenshare frames — ignore webcam frames
        frame_type = inner.get("type", "")
        if frame_type != "screenshare":
            return

        # Extract base64 PNG from buffer field
        b64_buffer = inner.get("buffer", "")
        if not b64_buffer:
            return

        import base64
        try:
            image_bytes = base64.b64decode(b64_buffer)
        except Exception:
            logger.warning("Failed to decode base64 video frame for bot %s", bot_id[:8])
            return

        engine = get_bot_engine()
        session = await engine.get_or_recover_session(bot_id)
        if not session or not session.screen_capture:
            return

        result = await session.screen_capture.handle_screenshot(image_bytes)

        # Speak the video-apology aloud if this is the first video detection
        from app.meeting.screen_capture import CaptureOutcome
        if result.outcome == CaptureOutcome.VIDEO and result.apology:
            if engine._tts:
                import asyncio as _asyncio
                loop = _asyncio.get_running_loop()
                try:
                    audio = await loop.run_in_executor(
                        None, lambda: engine._tts.synthesize(result.apology)
                    )
                    if audio:
                        await engine._recall_client.send_audio(bot_id, audio)
                        logger.info("Spoke video-apology for bot %s", bot_id[:8])
                except Exception as exc:
                    logger.warning("Failed to speak video apology: %s", exc)

    except Exception as exc:
        logger.error("Error processing video frame webhook: %s", exc, exc_info=True)


async def _handle_screenshare_event(event: str, data: dict) -> None:
    """Process participant_events.screenshare_on/off events.

    Resets ScreenCaptureManager state when a participant stops sharing
    so the next share starts fresh (no stale hash from previous session).
    """
    try:
        bot_id = ""
        bot_obj = data.get("bot", {})
        if isinstance(bot_obj, dict):
            bot_id = bot_obj.get("id", "")
        if not bot_id:
            return

        engine = get_bot_engine()
        session = await engine.get_or_recover_session(bot_id)
        if not session or not session.screen_capture:
            return

        participant = data.get("data", {}).get("participant", {})
        name = participant.get("name", "unknown") if isinstance(participant, dict) else "unknown"

        if event == "participant_events.screenshare_on":
            logger.info("Screen share started by %s (bot %s)", name, bot_id[:8])
            # Reset hash so first frame of new share is always processed
            session.screen_capture.reset_for_new_share()
        else:
            logger.info("Screen share stopped by %s (bot %s)", name, bot_id[:8])
            session.screen_capture.reset_for_new_share()

    except Exception as exc:
        logger.error("Error processing screenshare event: %s", exc, exc_info=True)


async def _send_greeting(bot_id: str) -> None:
    """Send an intro greeting immediately when the bot joins the call."""
    try:
        engine = get_bot_engine()
        # Use centralized model initialization (thread-safe, double-checked)
        await engine._lazy_load_models()

        # Pull agent name, wake word, and persona from the session config.
        session_id = engine._sessions_by_bot_id.get(bot_id)
        session = engine.sessions.get(session_id) if session_id else None
        agent_name = "your AI assistant"
        wake_phrase = "Hey Nova"
        persona_id = "general"
        if session:
            name = session.agent_config.get("agent_name", "")
            if name:
                agent_name = name
            ww = session.agent_config.get("wake_word", "nova")
            wake_phrase = ww.title()
            persona_id = session.agent_config.get("persona_id", "general")

        greeting = (
            f"Hi everyone, I'm {agent_name} for this meeting. "
            f"Ask me anything by saying {wake_phrase} followed by your question."
        )
        async with engine._tts_lock:
            if not engine._tts:
                from app.core.tts import TextToSpeech

                engine._tts = TextToSpeech(
                    voice=get_persona_tts_voice(persona_id),
                    sample_rate=24000,
                    speed=1.1,
                )
                engine._filler_manager.preload(engine._tts)
                engine._models_loaded = True
            else:
                target_voice = get_persona_tts_voice(persona_id)
                if engine._tts.voice != target_voice:
                    engine._tts.voice = target_voice
                    engine._filler_manager.preload(engine._tts)
            audio = engine._tts.synthesize(greeting)
        if audio:
            await engine._recall_client.send_audio(bot_id, audio)
            # Track greeting text for echo detection
            _recent_bot_output.setdefault(bot_id, []).append(greeting.lower())
            logger.info("Greeting sent for bot %s", bot_id[:8])
    except Exception as exc:
        logger.warning("Failed to send greeting: %s", exc)
