"""Recall.ai webhook endpoint.

Receives real-time transcription and bot status events from Recall.ai.
Returns 200 immediately and processes events in background tasks
to avoid webhook timeouts.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Meeting, AsyncSessionLocal

logger = logging.getLogger(__name__)

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


@router.post("/recall")
async def recall_webhook(request: Request):
    """Receive events from Recall.ai.

    Returns 200 immediately. Processing happens in a background task
    to keep webhook response time under Recall.ai's timeout.
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Invalid JSON in webhook payload")
        return {"status": "error", "message": "invalid json"}

    # Log raw payload at debug level
    import json
    logger.debug("WEBHOOK RAW: %s", json.dumps(payload, default=str)[:2000])

    event = payload.get("event", "")
    data = payload.get("data", {})

    # Route to the correct handler — only one task per webhook
    handled = False
    if event:
        if "transcript" in event.lower():
            asyncio.create_task(_handle_transcription(data))
            handled = True
        elif "status" in event.lower():
            asyncio.create_task(_handle_status_change(data))
            handled = True

    if not handled and not event:
        # No event field — direct transcript webhook
        if "bot_id" in payload or "words" in payload or "text" in payload:
            asyncio.create_task(_handle_transcription(payload))

    return {"status": "ok"}


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

        if isinstance(inner_data, dict):
            # Speaker from participant
            participant = inner_data.get("participant", {})
            if isinstance(participant, dict):
                speaker = participant.get("name", "")

            # Text from words array
            words = inner_data.get("words", [])
            if words and isinstance(words, list):
                text = " ".join(
                    w.get("text", "") for w in words if isinstance(w, dict)
                )

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

        logger.warning("TRANSCRIPT [%s] %s: %s", bot_id[:8] if bot_id else "?", speaker, text[:120])

        # Fallback greeting: if status webhook didn't fire, greet on first transcript
        if bot_id and bot_id not in _greeted_bots:
            _greeted_bots.add(bot_id)
            await _send_greeting(bot_id)

        await engine.process_webhook_transcript(bot_id, speaker, text)

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
        if not engine._tts:
            from app.core.tts import TextToSpeech
            engine._tts = TextToSpeech(voice="am_michael", sample_rate=24000, speed=1.1)
            engine._filler_manager.preload(engine._tts)
            engine._models_loaded = True

        # Pull agent name and wake word from the session config
        session_id = engine._sessions_by_bot_id.get(bot_id)
        session = engine.sessions.get(session_id) if session_id else None
        agent_name = "your AI assistant"
        wake_phrase = "Hey Assistant"
        if session:
            name = session.agent_config.get("agent_name", "")
            if name:
                agent_name = name
            ww = session.agent_config.get("wake_word", "")
            if ww:
                wake_phrase = ww.title()

        greeting = (
            f"Hi everyone, I'm {agent_name} for this meeting. "
            f"Ask me anything by saying {wake_phrase} followed by your question."
        )
        audio = engine._tts.synthesize(greeting)
        if audio:
            await engine._recall_client.send_audio(bot_id, audio)
            # Track greeting text for echo detection
            _recent_bot_output.setdefault(bot_id, []).append(greeting.lower())
            logger.warning("Greeting sent for bot %s", bot_id[:8])
    except Exception as exc:
        logger.warning("Failed to send greeting: %s", exc)
