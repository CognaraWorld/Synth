"""Tests for the shared BotEngine singleton wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.api import websocket
from app.api.routes import webhook
from app.core.engine_singleton import set_engine
from app.meeting.live_control import LiveSessionService


def test_webhook_websocket_and_live_control_share_engine_singleton() -> None:
    engine = MagicMock()
    set_engine(engine)
    try:
        assert webhook.get_bot_engine() is engine
        assert websocket.get_engine() is engine

        service = LiveSessionService(db=MagicMock())
        assert service.engine is engine
    finally:
        set_engine(None)
