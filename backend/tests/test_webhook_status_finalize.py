"""Terminal Recall.ai status webhook → DB update → auto-finalize scheduling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_status_done_updates_meeting_and_schedules_finalize() -> None:
    from app.api.routes import webhook as wh

    bot_id = "recall-bot-test-123"
    meeting_id = uuid4()
    user_id = uuid4()

    meeting = SimpleNamespace(
        id=meeting_id,
        status="active",
        bot_id=bot_id,
        transcript=None,
        started_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        credits_used=0,
        user_id=user_id,
    )

    meeting_result = MagicMock()
    meeting_result.scalar_one_or_none.return_value = meeting
    bill_result = MagicMock()
    bill_result.rowcount = 1
    user_update_result = MagicMock()
    email_result = MagicMock()
    email_result.first.return_value = ("owner@example.com",)

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[meeting_result, bill_result, user_update_result, email_result],
    )
    db.commit = AsyncMock()

    class _SessionCtx:
        async def __aenter__(self_inner):
            return db

        async def __aexit__(self_inner, *args):
            return None

    mock_engine = MagicMock()
    mock_engine._sessions_by_bot_id.get.return_value = None

    scheduled: list = []

    def _capture_task(coro):
        scheduled.append(coro)
        t = MagicMock()
        t.add_done_callback = MagicMock()
        return t

    payload = {"bot": {"id": bot_id}, "status": {"code": "done"}}

    with (
        patch.object(wh, "cleanup_bot_tracking", new_callable=MagicMock),
        patch.object(wh, "get_bot_engine", return_value=mock_engine),
        patch.object(wh, "AsyncSessionLocal", MagicMock(side_effect=lambda: _SessionCtx())),
        patch.object(wh, "_auto_finalize_report", new_callable=AsyncMock) as fin,
        patch("asyncio.create_task", side_effect=_capture_task),
    ):
        await wh._handle_status_change(payload)

    assert meeting.status == "ended"
    db.commit.assert_awaited()
    assert len(scheduled) == 1
    await scheduled[0]
    fin.assert_awaited_once_with(meeting_id, "owner@example.com")


@pytest.mark.asyncio
async def test_status_done_still_schedules_finalize_when_meeting_already_ended() -> None:
    from app.api.routes import webhook as wh

    bot_id = "recall-bot-test-ended"
    meeting_id = uuid4()
    user_id = uuid4()

    meeting = SimpleNamespace(
        id=meeting_id,
        status="ended",
        bot_id=bot_id,
        transcript="Alice: Existing transcript.",
        started_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        credits_used=5,
        user_id=user_id,
    )

    meeting_result = MagicMock()
    meeting_result.scalar_one_or_none.return_value = meeting
    email_result = MagicMock()
    email_result.first.return_value = ("owner@example.com",)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[meeting_result, email_result])
    db.commit = AsyncMock()

    class _SessionCtx:
        async def __aenter__(self_inner):
            return db

        async def __aexit__(self_inner, *args):
            return None

    mock_engine = MagicMock()
    mock_engine._sessions_by_bot_id.get.return_value = None

    scheduled: list = []

    def _capture_task(coro):
        scheduled.append(coro)
        task = MagicMock()
        task.add_done_callback = MagicMock()
        return task

    payload = {"bot": {"id": bot_id}, "status": {"code": "done"}}

    with (
        patch.object(wh, "cleanup_bot_tracking", new_callable=MagicMock),
        patch.object(wh, "get_bot_engine", return_value=mock_engine),
        patch.object(wh, "AsyncSessionLocal", MagicMock(side_effect=lambda: _SessionCtx())),
        patch.object(wh, "_auto_finalize_report", new_callable=AsyncMock) as fin,
        patch("asyncio.create_task", side_effect=_capture_task),
    ):
        await wh._handle_status_change(payload)

    assert len(scheduled) == 1
    await scheduled[0]
    fin.assert_awaited_once_with(meeting_id, "owner@example.com")
