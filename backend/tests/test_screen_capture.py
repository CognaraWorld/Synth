"""Tests for screenshare frame deduplication and webhook recovery flow."""

from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import webhook
from app.models.schemas import MeetingCreate
from app.meeting.screen_capture import CaptureOutcome, CaptureResult, ScreenCaptureManager


class _FakeContext:
    def __init__(self) -> None:
        self.entries: list[str] = []

    def add_screen_content(self, content: str) -> None:
        self.entries.append(content)


class _FakeGemini:
    def __init__(self) -> None:
        self.calls = 0

    async def extract_screen_content(self, image_bytes: bytes) -> str:
        self.calls += 1
        return f"frame-{self.calls}"


@pytest.mark.asyncio
async def test_screen_capture_skips_non_consecutive_duplicate_frames() -> None:
    context = _FakeContext()
    gemini = _FakeGemini()
    manager = ScreenCaptureManager(
        session_id="session-1",
        context_manager=context,
        gemini=gemini,
    )

    first = await manager.handle_screenshot(b"A")
    second = await manager.handle_screenshot(b"B")
    third = await manager.handle_screenshot(b"A")

    assert first.outcome == CaptureOutcome.EXTRACTED
    assert second.outcome == CaptureOutcome.EXTRACTED
    assert third.outcome == CaptureOutcome.SKIPPED
    assert gemini.calls == 2
    assert context.entries == ["frame-1", "frame-2"]


@pytest.mark.asyncio
async def test_reset_for_new_share_allows_reprocessing_same_frame() -> None:
    context = _FakeContext()
    gemini = _FakeGemini()
    manager = ScreenCaptureManager(
        session_id="session-2",
        context_manager=context,
        gemini=gemini,
    )

    await manager.handle_screenshot(b"A")
    manager.reset_for_new_share()
    result = await manager.handle_screenshot(b"A")

    assert result.outcome == CaptureOutcome.EXTRACTED
    assert gemini.calls == 2
    assert context.entries == ["frame-1", "frame-2"]


@pytest.mark.asyncio
async def test_screen_capture_serializes_concurrent_duplicate_frames() -> None:
    context = _FakeContext()
    gemini = _FakeGemini()
    manager = ScreenCaptureManager(
        session_id="session-3",
        context_manager=context,
        gemini=gemini,
    )

    results = await asyncio.gather(
        *[manager.handle_screenshot(b"same-frame") for _ in range(5)]
    )

    extracted = [result for result in results if result.outcome == CaptureOutcome.EXTRACTED]
    skipped = [result for result in results if result.outcome == CaptureOutcome.SKIPPED]
    assert len(extracted) == 1
    assert len(skipped) == 4
    assert gemini.calls == 1
    assert context.entries == ["frame-1"]


@pytest.mark.asyncio
async def test_video_frame_handler_recovers_missing_session_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    capture = SimpleNamespace(
        handle_screenshot=AsyncMock(return_value=CaptureResult(outcome=CaptureOutcome.EXTRACTED)),
    )
    session = SimpleNamespace(screen_capture=capture)
    engine = MagicMock()
    engine.get_or_recover_session = AsyncMock(return_value=session)
    engine._tts = None
    engine._recall_client = MagicMock()

    monkeypatch.setattr(webhook, "get_bot_engine", lambda: engine)

    payload = {
        "bot": {"id": "bot-1"},
        "data": {
            "type": "screenshare",
            "buffer": base64.b64encode(b"img-A").decode("ascii"),
        },
    }
    await webhook._handle_video_frame(payload)

    engine.get_or_recover_session.assert_awaited_once_with("bot-1")
    capture.handle_screenshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_screenshare_event_handler_recovers_missing_session_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = SimpleNamespace(reset_for_new_share=MagicMock())
    session = SimpleNamespace(screen_capture=capture)
    engine = MagicMock()
    engine.get_or_recover_session = AsyncMock(return_value=session)

    monkeypatch.setattr(webhook, "get_bot_engine", lambda: engine)

    payload = {
        "bot": {"id": "bot-2"},
        "data": {"participant": {"name": "Alice"}},
    }
    await webhook._handle_screenshare_event("participant_events.screenshare_on", payload)

    engine.get_or_recover_session.assert_awaited_once_with("bot-2")
    capture.reset_for_new_share.assert_called_once()


@pytest.mark.asyncio
async def test_create_meeting_requires_gemini_key_when_recall_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes.meetings import create_meeting

    current_user = MagicMock(id=uuid4(), credits=3)
    primary_agent = MagicMock(
        id=uuid4(),
        is_primary=True,
        name="Synth",
        mode="general",
        description="",
        system_prompt="",
        voice="female",
    )

    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [primary_agent]

    db = AsyncMock()
    db.execute.return_value = query_result
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    settings = SimpleNamespace(
        recall_api_key="recall-test-key",
        gemini_api_key="",
        webhook_base_url="https://example.com",
    )
    monkeypatch.setattr("app.api.routes.meetings.get_settings", lambda: settings)

    with pytest.raises(HTTPException, match="GEMINI_API_KEY"):
        await create_meeting(
            meeting_data=MeetingCreate(meeting_link="https://zoom.us/j/123456789"),
            current_user=current_user,
            db=db,
        )
