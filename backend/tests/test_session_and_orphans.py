"""Tests for session scope identity and orphaned bot DB reconciliation."""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.meeting.session import MeetingSession


class TestSessionContextScope:
    """Fix #1: ContextManager must receive the persistent meeting_id,
    not the ephemeral session_id."""

    def test_context_manager_receives_meeting_id_not_session_id(self) -> None:
        meeting_id = str(uuid4())
        session = MeetingSession(meeting_id=meeting_id)

        # The context manager must be scoped to the real meeting id
        assert session.context_manager.meeting_id == meeting_id
        # And it must NOT be the ephemeral session id
        assert session.context_manager.meeting_id != session.session_id

    def test_session_recovery_preserves_meeting_scope(self) -> None:
        """Simulate session recreation (e.g. after --reload) and confirm
        that a new session for the same meeting scopes to the same id."""
        meeting_id = str(uuid4())

        session_a = MeetingSession(meeting_id=meeting_id)
        session_b = MeetingSession(meeting_id=meeting_id)

        # Different sessions
        assert session_a.session_id != session_b.session_id
        # Same meeting scope
        assert session_a.context_manager.meeting_id == session_b.context_manager.meeting_id
        assert session_a.context_manager.meeting_id == meeting_id

    def test_agent_config_forwarded_to_context_manager(self) -> None:
        agent_id = str(uuid4())
        user_id = str(uuid4())
        meeting_id = str(uuid4())

        session = MeetingSession(
            meeting_id=meeting_id,
            agent_config={"agent_id": agent_id, "user_id": user_id},
        )

        assert session.context_manager.agent_id == agent_id
        assert session.context_manager.user_id == user_id


class TestOrphanBotReconciliation:
    """Fix #2: _stop_orphaned_bots must transition meetings to ended state
    and run billing settlement."""

    @pytest.mark.asyncio
    async def test_orphan_with_bot_stopped_and_meeting_reconciled(self) -> None:
        meeting_id = uuid4()
        user_id = uuid4()
        started_at = datetime.now(timezone.utc) - timedelta(minutes=30)

        meeting = MagicMock(
            id=meeting_id,
            user_id=user_id,
            bot_id="bot-abc123def",
            status="active",
            started_at=started_at,
            ended_at=None,
            credits_used=0,
        )

        # Build mock DB
        mock_db = AsyncMock()
        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [meeting]

        # update() returns a result with rowcount=1 (billing success)
        update_result = MagicMock()
        update_result.rowcount = 1
        mock_db.execute.side_effect = [select_result, update_result, update_result]
        mock_db.commit = AsyncMock()

        mock_recall = MagicMock()
        mock_recall.stop_bot = AsyncMock()
        mock_recall.close = AsyncMock()

        # Create a proper async context manager for AsyncSessionLocal
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch.dict("sys.modules", {}):
            from app import main as main_module

            with patch.object(main_module, "__name__", "app.main"):
                # Patch the imports that happen inside _stop_orphaned_bots
                mock_async_session = MagicMock(return_value=mock_session_ctx)
                mock_meeting_cls = MagicMock()
                mock_meeting_cls.status = "active"
                mock_meeting_cls.bot_id.isnot.return_value = True

                with patch("app.models.database.AsyncSessionLocal", mock_async_session), \
                     patch("app.meeting.recall_client.RecallClient", return_value=mock_recall):
                    await main_module._stop_orphaned_bots()

        mock_recall.stop_bot.assert_awaited_once_with("bot-abc123def")
        mock_recall.close.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_orphan_without_bot_id_still_reconciled(self) -> None:
        """Meetings stuck as active with no bot_id should still be moved
        to ended state (bot already gone scenario)."""
        meeting = MagicMock(
            id=uuid4(),
            user_id=uuid4(),
            bot_id=None,
            status="active",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            ended_at=None,
            credits_used=0,
        )

        mock_db = AsyncMock()
        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [meeting]

        update_result = MagicMock()
        update_result.rowcount = 1
        mock_db.execute.side_effect = [select_result, update_result, update_result]
        mock_db.commit = AsyncMock()

        mock_recall = MagicMock()
        mock_recall.stop_bot = AsyncMock()
        mock_recall.close = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        from app import main as main_module

        with patch("app.models.database.AsyncSessionLocal", MagicMock(return_value=mock_session_ctx)), \
             patch("app.meeting.recall_client.RecallClient", return_value=mock_recall):
            await main_module._stop_orphaned_bots()

        # stop_bot should NOT be called (no bot_id)
        mock_recall.stop_bot.assert_not_awaited()
        # DB should still be committed (meeting reconciled)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_orphans_skips_all_work(self) -> None:
        mock_db = AsyncMock()
        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = select_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        from app import main as main_module

        with patch("app.models.database.AsyncSessionLocal", MagicMock(return_value=mock_session_ctx)):
            await main_module._stop_orphaned_bots()

        # No orphans means no commit needed
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_zero_duration_orphan_skips_billing_delta(self) -> None:
        meeting = MagicMock(
            id=uuid4(),
            user_id=uuid4(),
            bot_id=None,
            status="active",
            started_at=None,
            ended_at=None,
            credits_used=0,
        )

        mock_db = AsyncMock()
        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [meeting]
        mock_db.execute.return_value = select_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        from app import main as main_module

        with patch("app.models.database.AsyncSessionLocal", MagicMock(return_value=mock_session_ctx)):
            await main_module._stop_orphaned_bots()

        assert mock_db.execute.await_count == 1
        assert meeting.status == "ended"
        mock_db.commit.assert_awaited_once()
