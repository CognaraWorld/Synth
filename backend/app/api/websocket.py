"""WebSocket endpoint for live meeting status and transcript streaming.

Provides real-time updates to the frontend during an active meeting
session, including state transitions, live transcript segments, and
error notifications.

Phase 6 implementation.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from app.config import get_settings
from app.core.bot_engine import BotEngine, SessionNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Shared BotEngine instance — initialized once and reused across
# WebSocket connections. Created lazily on first access.
_engine: BotEngine | None = None


def get_engine() -> BotEngine:
    """Return the shared BotEngine singleton.

    Creates the instance on first call. This avoids loading heavy
    models at import time while ensuring all WebSocket connections
    share the same engine state.

    Returns:
        The shared BotEngine instance.
    """
    global _engine
    if _engine is None:
        _engine = BotEngine()
    return _engine


def set_engine(engine: BotEngine) -> None:
    """Override the shared BotEngine instance (useful for testing).

    Args:
        engine: A BotEngine instance to use as the singleton.
    """
    global _engine
    _engine = engine


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """Stream live meeting status and transcript over WebSocket.

    Authenticates via a JWT token passed as a ``token`` query parameter
    before accepting the connection (OWASP A01:2021 - Broken Access Control).

    After accepting the connection, this endpoint enters a polling
    loop that sends periodic status and transcript updates to the
    connected client as JSON messages.

    Message types sent to the client:

    - ``{"type": "status", "state": "<state>", "duration": <float>}``
      Sent whenever the session state changes or on each poll tick.

    - ``{"type": "transcript", "text": "...", "speaker": "...", "timestamp": "..."}``
      Sent when new transcript text is available.

    - ``{"type": "error", "message": "..."}``
      Sent when an error occurs (e.g. session not found).

    - ``{"type": "ended", "duration": <float>}``
      Sent once when the session reaches a terminal state.

    Args:
        websocket: The incoming WebSocket connection.
        session_id: The meeting session ID to stream updates for.
    """
    # Authenticate via JWT token in query params before accepting.
    # WebSocket connections cannot use standard Authorization headers,
    # so the token is passed as a query parameter instead.
    settings = get_settings()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Reject tokens signed with the default insecure key
    if settings.secret_key == "change-me-in-production":
        await websocket.close(code=4001, reason="Authentication not configured")
        return

    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except (JWTError, Exception):
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify the authenticated user owns this session (prevent IDOR)
    # Fail-closed: reject if session not found or ownership can't be verified
    engine = get_engine()
    session_obj = engine.sessions.get(session_id)
    if not session_obj:
        await websocket.close(code=4004, reason="Session not found")
        return

    if session_obj.bot_id:
        try:
            from uuid import UUID as _UUID
            from sqlalchemy import select
            from app.models.database import Meeting, AsyncSessionLocal
            parsed_uid = _UUID(user_id)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Meeting).where(
                        Meeting.bot_id == session_obj.bot_id,
                        Meeting.user_id == parsed_uid,
                    )
                )
                if not result.scalar_one_or_none():
                    await websocket.close(code=4003, reason="Access denied")
                    return
        except ValueError:
            await websocket.close(code=4001, reason="Invalid user identity")
            return
        except Exception as exc:
            logger.warning("WebSocket ownership check failed: %s", exc)
            await websocket.close(code=4003, reason="Access denied")
            return

    await websocket.accept()
    logger.info("WebSocket connected for session %s (user %s)", session_id, user_id)

    engine = get_engine()

    # Track the last known transcript length so we only send new text
    last_transcript_len: int = 0
    last_state: str | None = None
    poll_interval: float = 0.5  # seconds

    try:
        while True:
            try:
                status = await engine.get_status(session_id)
            except SessionNotFoundError:
                await _send_json(websocket, {
                    "type": "error",
                    "message": f"Session {session_id} not found",
                })
                break

            current_state = status.get("state", "unknown")

            # Send status update if state changed
            if current_state != last_state:
                await _send_json(websocket, {
                    "type": "status",
                    "state": current_state,
                    "duration": status.get("duration_seconds", 0),
                    "is_active": status.get("is_active", False),
                })
                last_state = current_state

            # Send new transcript text if available
            session = engine.sessions.get(session_id)
            if session is not None:
                full_text = session.context_manager.raw_buffer.get_full_text()
                if len(full_text) > last_transcript_len:
                    new_text = full_text[last_transcript_len:]
                    last_transcript_len = len(full_text)
                    await _send_json(websocket, {
                        "type": "transcript",
                        "text": new_text,
                        "speaker": "participant",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            # Check for terminal state
            if current_state in ("ended", "failed"):
                await _send_json(websocket, {
                    "type": "ended",
                    "state": current_state,
                    "duration": status.get("duration_seconds", 0),
                })
                break

            # Check for incoming client messages (non-blocking)
            try:
                client_msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=poll_interval,
                )
                await _handle_client_message(client_msg, session_id, websocket, engine)
            except asyncio.TimeoutError:
                # No client message within the poll interval — continue loop
                pass

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception as exc:
        logger.error(
            "WebSocket error for session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        try:
            await _send_json(websocket, {
                "type": "error",
                "message": "Internal server error",
            })
        except Exception:
            pass
    finally:
        logger.info("WebSocket closed for session %s", session_id)


async def _send_json(websocket: WebSocket, data: dict) -> None:
    """Send a JSON message over the WebSocket.

    Args:
        websocket: The WebSocket connection.
        data: Dictionary to serialize and send.
    """
    await websocket.send_text(json.dumps(data))


async def _handle_client_message(
    raw_message: str,
    session_id: str,
    websocket: WebSocket,
    engine: BotEngine,
) -> None:
    """Handle an incoming message from the WebSocket client.

    Supported client commands:

    - ``{"action": "stop"}`` — stop the meeting session.
    - ``{"action": "status"}`` — request an immediate status update.

    Args:
        raw_message: Raw JSON string from the client.
        session_id: The session this WebSocket is connected to.
        websocket: The WebSocket connection for sending replies.
        engine: The BotEngine instance.
    """
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        await _send_json(websocket, {
            "type": "error",
            "message": "Invalid JSON",
        })
        return

    action = message.get("action")

    if action == "stop":
        try:
            result = await engine.stop_meeting(session_id)
            await _send_json(websocket, {
                "type": "ended",
                "state": "ended",
                "duration": result.get("duration_seconds", 0),
            })
        except SessionNotFoundError:
            await _send_json(websocket, {
                "type": "error",
                "message": f"Session {session_id} not found",
            })

    elif action == "status":
        try:
            status = await engine.get_status(session_id)
            await _send_json(websocket, {
                "type": "status",
                "state": status.get("state", "unknown"),
                "duration": status.get("duration_seconds", 0),
                "is_active": status.get("is_active", False),
            })
        except SessionNotFoundError:
            await _send_json(websocket, {
                "type": "error",
                "message": f"Session {session_id} not found",
            })

    else:
        await _send_json(websocket, {
            "type": "error",
            "message": f"Unknown action: {action!r}",
        })
