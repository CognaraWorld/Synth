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

logger = logging.getLogger(__name__)

# Bounded concurrency: limit parallel webhook processing to prevent
# resource exhaustion under burst traffic (OWASP A05:2021 - Security Misconfiguration)
_webhook_semaphore = asyncio.Semaphore(20)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Singleton BotEngine — initialized on first webhook hit
_bot_engine = None
_greeted_bots: set[str] = set()  # bot_ids that have already been greeted
_recent_bot_output: dict[str, list[str]] = {}  # bot_id -> recent bot output texts for echo detection


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
        if "transcript" in event.lower():
            _task = asyncio.create_task(_bounded_handle_transcription(data))
            _task.add_done_callback(lambda t: logger.error("Webhook transcript task failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)
            handled = True
        elif "status" in event.lower():
            _task = asyncio.create_task(_bounded_handle_status_change(data))
            _task.add_done_callback(lambda t: logger.error("Webhook status task failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)
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


async def _send_greeting(bot_id: str) -> None:
    """Send an intro greeting immediately when the bot joins the call."""
    try:
        engine = get_bot_engine()
        # Use centralized model initialization (thread-safe, double-checked)
        await engine._lazy_load_models()

        # Pull agent name, wake word, and persona from the session config
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

        engine._ensure_tts_voice_for_persona(persona_id)

        greeting = (
            f"Hi everyone, I'm {agent_name} for this meeting. "
            f"Ask me anything by saying {wake_phrase} followed by your question."
        )
        audio = engine._tts.synthesize(greeting)
        if audio:
            await engine._recall_client.send_audio(bot_id, audio)
            # Track greeting text for echo detection
            _recent_bot_output.setdefault(bot_id, []).append(greeting.lower())
            logger.info("Greeting sent for bot %s", bot_id[:8])
    except Exception as exc:
        logger.warning("Failed to send greeting: %s", exc)
