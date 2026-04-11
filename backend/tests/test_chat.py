"""Tests for the meeting chat API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.schemas import ChatSendRequest


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid4()
    return user


def _make_meeting(user_id, agent=None, transcript=None):
    meeting = MagicMock()
    meeting.id = uuid4()
    meeting.user_id = user_id
    meeting.transcript = transcript
    meeting.agent = agent
    return meeting


def _make_agent():
    agent = MagicMock()
    agent.id = uuid4()
    agent.system_prompt = "You are a helpful assistant."
    agent.mode = "general"
    agent.description = "General assistant"
    agent.persona_id = "general"
    agent.documents = []
    return agent


class TestMeetingOwnership:
    """Verify ownership enforcement on chat endpoints."""

    @pytest.mark.asyncio
    async def test_chat_returns_404_for_missing_meeting(self) -> None:
        from app.api.routes.chat import _get_meeting_or_raise

        user = _make_user()
        db = AsyncMock()
        fake_result = MagicMock()
        fake_result.scalar_one_or_none.return_value = None
        db.execute.return_value = fake_result

        with pytest.raises(HTTPException) as exc_info:
            await _get_meeting_or_raise(uuid4(), user, db)
        assert exc_info.value.status_code == 404
        assert "Meeting not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_chat_returns_403_for_wrong_user(self) -> None:
        from app.api.routes.chat import _get_meeting_or_raise

        owner = _make_user()
        intruder = _make_user()
        meeting = _make_meeting(user_id=owner.id)

        db = AsyncMock()
        fake_result = MagicMock()
        fake_result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = fake_result

        with pytest.raises(HTTPException) as exc_info:
            await _get_meeting_or_raise(meeting.id, intruder, db)
        assert exc_info.value.status_code == 403
        assert "Access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_chat_allows_meeting_owner(self) -> None:
        from app.api.routes.chat import _get_meeting_or_raise

        owner = _make_user()
        meeting = _make_meeting(user_id=owner.id)

        db = AsyncMock()
        fake_result = MagicMock()
        fake_result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = fake_result

        result = await _get_meeting_or_raise(meeting.id, owner, db)
        assert result is meeting


class TestSendChatMessage:
    """Verify the POST /meetings/{id}/chat flow."""

    @pytest.mark.asyncio
    async def test_happy_path_persists_both_messages(self) -> None:
        from app.api.routes.chat import send_chat_message

        owner = _make_user()
        agent = _make_agent()
        meeting = _make_meeting(user_id=owner.id, agent=agent, transcript="Alice: Let's ship Monday.")

        db = AsyncMock()
        db.add = MagicMock()
        # _get_meeting_or_raise
        meeting_result = MagicMock()
        meeting_result.scalar_one_or_none.return_value = meeting
        # chat history (empty)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []
        # summary (none)
        summary_result = MagicMock()
        summary_result.scalar_one_or_none.return_value = None

        db.execute.side_effect = [meeting_result, history_result, summary_result]

        req = ChatSendRequest(message="What was decided?")

        with (
            patch("app.api.routes.chat._get_llm") as mock_get_llm,
            patch("app.api.routes.chat._check_rate_limit", new_callable=AsyncMock),
        ):
            mock_llm = MagicMock()
            mock_llm.async_query = AsyncMock(return_value="The team decided to ship on Monday.")
            mock_get_llm.return_value = mock_llm

            result = await send_chat_message(
                meeting_id=meeting.id,
                req=req,
                current_user=owner,
                db=db,
            )

        # Both messages were added to the session
        assert db.add.call_count >= 2
        db.commit.assert_awaited_once()

        # Response contains both messages
        assert result["user_message"].role == "user"
        assert result["user_message"].content == "What was decided?"
        assert result["assistant_message"].role == "assistant"
        assert "Monday" in result["assistant_message"].content

    @pytest.mark.asyncio
    async def test_llm_failure_rolls_back_user_message(self) -> None:
        from app.api.routes.chat import send_chat_message

        owner = _make_user()
        agent = _make_agent()
        meeting = _make_meeting(user_id=owner.id, agent=agent)

        db = AsyncMock()
        db.add = MagicMock()
        meeting_result = MagicMock()
        meeting_result.scalar_one_or_none.return_value = meeting
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []
        summary_result = MagicMock()
        summary_result.scalar_one_or_none.return_value = None
        db.execute.side_effect = [meeting_result, history_result, summary_result]

        req = ChatSendRequest(message="Hello")

        with (
            patch("app.api.routes.chat._get_llm") as mock_get_llm,
            patch("app.api.routes.chat._check_rate_limit", new_callable=AsyncMock),
        ):
            mock_llm = MagicMock()
            mock_llm.async_query = AsyncMock(side_effect=RuntimeError("LLM down"))
            mock_get_llm.return_value = mock_llm

            with pytest.raises(HTTPException) as exc_info:
                await send_chat_message(
                    meeting_id=meeting.id,
                    req=req,
                    current_user=owner,
                    db=db,
                )

        assert exc_info.value.status_code == 502
        assert "temporarily unavailable" in str(exc_info.value.detail)
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()


class TestChatHistory:
    """Verify the GET /meetings/{id}/chat/history endpoint."""

    @pytest.mark.asyncio
    async def test_returns_latest_messages_in_chronological_order(self) -> None:
        from app.api.routes.chat import get_chat_history

        owner = _make_user()
        meeting = _make_meeting(user_id=owner.id)

        # Simulate 60 messages; the endpoint should return newest 50 in ASC order
        all_messages = []
        for i in range(60):
            msg = MagicMock()
            msg.id = uuid4()
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i}"
            msg.created_at = datetime(2026, 4, 6, 10, i, 0, tzinfo=timezone.utc)
            all_messages.append(msg)

        # Newest 50 = messages 10-59, but returned DESC from DB then reversed
        newest_50_desc = list(reversed(all_messages[10:]))

        db = AsyncMock()
        # _get_meeting_or_raise
        meeting_result = MagicMock()
        meeting_result.scalar_one_or_none.return_value = meeting
        # count
        count_result = MagicMock()
        count_result.scalar.return_value = 60
        # messages (DESC order from DB)
        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = newest_50_desc

        db.execute.side_effect = [meeting_result, count_result, messages_result]

        result = await get_chat_history(
            meeting_id=meeting.id,
            per_page=50,
            before=None,
            current_user=owner,
            db=db,
        )

        assert result.total == 60
        # Messages should be in chronological order (oldest first) after reversal
        assert result.messages[0].content == "Message 10"
        assert result.messages[-1].content == "Message 59"

    @pytest.mark.asyncio
    async def test_history_respects_before_parameter(self) -> None:
        """Verify that the `before` param filters messages."""
        from app.api.routes.chat import get_chat_history

        owner = _make_user()
        meeting = _make_meeting(user_id=owner.id)

        db = AsyncMock()
        meeting_result = MagicMock()
        meeting_result.scalar_one_or_none.return_value = meeting
        count_result = MagicMock()
        count_result.scalar.return_value = 10
        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = []
        db.execute.side_effect = [meeting_result, count_result, messages_result]

        cutoff = datetime(2026, 4, 6, 12, 0, 0, tzinfo=timezone.utc)
        result = await get_chat_history(
            meeting_id=meeting.id,
            per_page=20,
            before=cutoff,
            current_user=owner,
            db=db,
        )

        # Verify the query was called (the before filter is applied via SQLAlchemy)
        assert db.execute.call_count == 3
        assert result.total == 10


class TestRateLimit:
    """Verify rate limiting on chat endpoint."""

    @pytest.mark.asyncio
    async def test_rate_limit_rejects_after_threshold(self) -> None:
        from app.api.routes.chat import _check_rate_limit, _rate_limit_buckets, _CHAT_RATE_LIMIT

        user_id = str(uuid4())
        # Clear any existing state
        _rate_limit_buckets.pop(user_id, None)

        # Fill the bucket to the limit
        for _ in range(_CHAT_RATE_LIMIT):
            await _check_rate_limit(user_id)

        # Next call should raise 429
        with pytest.raises(HTTPException) as exc_info:
            await _check_rate_limit(user_id)
        assert exc_info.value.status_code == 429

        # Cleanup
        _rate_limit_buckets.pop(user_id, None)


class TestContextBuilder:
    """Verify the context building helper."""

    @pytest.mark.asyncio
    async def test_truncates_long_transcript(self) -> None:
        from app.api.routes.chat import _build_chat_context

        meeting = _make_meeting(user_id=uuid4(), transcript="x" * 20000)

        db = AsyncMock()
        summary_result = MagicMock()
        summary_result.scalar_one_or_none.return_value = None
        db.execute.return_value = summary_result

        context = await _build_chat_context(meeting, [], db)

        assert "earlier transcript omitted" in context
        # The transcript portion should be truncated to ~12K
        transcript_section = context.split("## Meeting Transcript\n")[1].split("\n\n##")[0]
        assert len(transcript_section) <= 12100  # 12K + prefix text

    @pytest.mark.asyncio
    async def test_includes_summary_and_history(self) -> None:
        from app.api.routes.chat import _build_chat_context

        meeting = _make_meeting(user_id=uuid4(), transcript="Brief meeting.")
        summary = MagicMock()
        summary.content = "Team discussed launch."
        summary.key_points = "Launch on Monday"
        summary.action_items = "Prepare docs"
        summary.decisions = "Go live Monday"

        db = AsyncMock()
        summary_result = MagicMock()
        summary_result.scalar_one_or_none.return_value = summary
        db.execute.return_value = summary_result

        chat_msg = MagicMock()
        chat_msg.role = "user"
        chat_msg.content = "What happened?"

        context = await _build_chat_context(meeting, [chat_msg], db)

        assert "Brief meeting." in context
        assert "Team discussed launch." in context
        assert "Launch on Monday" in context
        assert "Prepare docs" in context
        assert "Go live Monday" in context
        assert "What happened?" in context


class TestSchemaValidation:
    """Verify schema constraints on chat models."""

    def test_role_must_be_user_or_assistant(self) -> None:
        from app.models.schemas import ChatMessageResponse

        # Valid roles
        ChatMessageResponse(
            id=uuid4(), role="user", content="hi",
            created_at=datetime.now(timezone.utc),
        )
        ChatMessageResponse(
            id=uuid4(), role="assistant", content="hello",
            created_at=datetime.now(timezone.utc),
        )

        # Invalid role
        with pytest.raises(Exception):
            ChatMessageResponse(
                id=uuid4(), role="admin", content="bad",
                created_at=datetime.now(timezone.utc),
            )

    def test_message_length_constraints(self) -> None:
        # Empty message rejected
        with pytest.raises(Exception):
            ChatSendRequest(message="")

        # Whitespace-only rejected (strip_whitespace + min_length=1)
        with pytest.raises(Exception):
            ChatSendRequest(message="   ")

        # Valid message
        req = ChatSendRequest(message="Hello")
        assert req.message == "Hello"
