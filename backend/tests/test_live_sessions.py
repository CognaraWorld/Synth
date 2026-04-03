"""Tests for the live session control plane and operator command tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.meeting.live_control import LiveSessionService, LiveSessionServiceError, ProviderActionResult
from app.models.credit_transaction import CreditTransaction  # noqa: F401
from app.models.database import Agent, LiveSession, Meeting, User


def _now() -> datetime:
    return datetime(2026, 4, 3, 14, 30, tzinfo=timezone.utc)


def _build_owned_meeting(*, status: str = "active", with_live_session: bool = True):
    now = _now()
    user = User(id=uuid4(), email="owner@example.com", name="Owner", credits=3)
    agent = Agent(
        id=uuid4(),
        user_id=user.id,
        name="Synth",
        description="Helpful assistant",
        system_prompt="Be concise",
        mode="general",
        created_at=now,
        updated_at=now,
    )
    meeting = Meeting(
        id=uuid4(),
        user_id=user.id,
        agent_id=agent.id,
        agent=agent,
        platform="zoom",
        meeting_link="https://zoom.us/j/123456789",
        status=status,
        created_at=now,
        started_at=now,
    )

    live_session = None
    if with_live_session:
        live_session = LiveSession(
            id=uuid4(),
            meeting_id=meeting.id,
            meeting=meeting,
            session_status="listening" if status == "active" else status,
            created_at=now,
            updated_at=now,
        )
        meeting.live_session = live_session

    return user, agent, meeting, live_session


def _build_engine_for_meeting(meeting: Meeting, *, state: str = "listening", transcript: str = ""):
    engine_session = MagicMock(
        session_id="session-123",
        meeting_id=str(meeting.id),
        bot_id="bot-123",
        operator_muted=False,
        output_stop_requested=False,
        last_instruction_at=None,
    )
    engine_session.get_state.return_value = state

    engine = MagicMock()
    engine.sessions = {engine_session.session_id: engine_session}
    engine.find_session_for_meeting.return_value = engine_session
    engine.get_transcript_text.return_value = transcript
    engine.submit_operator_instruction = MagicMock()
    engine.set_session_muted = MagicMock()
    engine.request_stop_speaking = MagicMock()
    engine.stop_meeting = AsyncMock(
        return_value={
            "transcript": transcript,
            "summary": "",
            "duration_seconds": 90.0,
        }
    )
    engine.join_meeting = AsyncMock(return_value=engine_session.session_id)
    return engine, engine_session


class TestLiveSessionService:
    @pytest.mark.asyncio
    async def test_activate_requires_provider_configuration_when_no_engine_session(self) -> None:
        user, _, meeting, _ = _build_owned_meeting(status="pending", with_live_session=False)
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = result
        db.add = MagicMock()

        provider = MagicMock()
        provider.is_configured.return_value = False

        engine = MagicMock()
        engine.find_session_for_meeting.return_value = None
        engine.sessions = {}

        service = LiveSessionService(db=db, engine=engine, provider=provider)

        with pytest.raises(LiveSessionServiceError, match="Recall.ai is not configured"):
            await service.activate_for_meeting(meeting.id, user)

    @pytest.mark.asyncio
    async def test_submit_instruction_applies_to_active_engine_session(self) -> None:
        user, _, meeting, live_session = _build_owned_meeting()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = result
        db.add = MagicMock()
        db.commit = AsyncMock()
        engine, engine_session = _build_engine_for_meeting(meeting)
        engine.submit_operator_instruction.side_effect = (
            lambda session_id, text: setattr(engine_session, "last_instruction_at", _now())
        )

        service = LiveSessionService(db=db, engine=engine, provider=MagicMock())
        response = await service.submit_instruction(meeting.id, user, "Do not mention pricing.")

        engine.submit_operator_instruction.assert_called_once_with(
            engine_session.session_id,
            "Do not mention pricing.",
        )
        assert response["delivery_status"] == "applied"
        assert response["instruction"] == "Do not mention pricing."
        assert live_session.last_instruction_at is not None

    @pytest.mark.asyncio
    async def test_set_mute_state_updates_engine_even_without_provider_keys(self) -> None:
        user, _, meeting, live_session = _build_owned_meeting()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = result
        db.commit = AsyncMock()

        provider = MagicMock()
        provider.mute = AsyncMock(
            return_value=ProviderActionResult(
                provider_status="not_configured",
                detail="Recall.ai credentials are not configured yet.",
            )
        )
        engine, engine_session = _build_engine_for_meeting(meeting)

        service = LiveSessionService(db=db, engine=engine, provider=provider)
        response = await service.set_mute_state(meeting.id, user, muted=True)

        engine.set_session_muted.assert_called_once_with(engine_session.session_id, True)
        assert live_session.is_muted is True
        assert response["provider_status"] == "not_configured"
        assert response["is_muted"] is True

    @pytest.mark.asyncio
    async def test_request_stop_speaking_records_placeholder_provider_status(self) -> None:
        user, _, meeting, live_session = _build_owned_meeting()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = result
        db.commit = AsyncMock()

        provider = MagicMock()
        provider.stop_speaking = AsyncMock(
            return_value=ProviderActionResult(
                provider_status="pending_integration",
                detail="Provider-side playback interruption is not wired yet.",
            )
        )
        engine, engine_session = _build_engine_for_meeting(meeting)

        service = LiveSessionService(db=db, engine=engine, provider=provider)
        response = await service.request_stop_speaking(meeting.id, user)

        engine.request_stop_speaking.assert_called_once_with(engine_session.session_id)
        assert live_session.stop_requested is True
        assert response["provider_status"] == "pending_integration"
        assert response["stop_requested"] is True

    @pytest.mark.asyncio
    async def test_leave_meeting_uses_engine_stop_and_persists_transcript(self) -> None:
        user, _, meeting, live_session = _build_owned_meeting()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = result
        db.commit = AsyncMock()
        engine, engine_session = _build_engine_for_meeting(
            meeting,
            state="responding",
            transcript="Alice: please capture the decision.",
        )

        service = LiveSessionService(db=db, engine=engine, provider=MagicMock())
        response = await service.leave_meeting(meeting.id, user)

        engine.stop_meeting.assert_awaited_once_with(engine_session.session_id)
        assert meeting.status == "ended"
        assert meeting.transcript == "Alice: please capture the decision."
        assert live_session.session_status == "ended"
        assert response["provider_status"] == "engine_stop"

    @pytest.mark.asyncio
    async def test_get_transcript_snapshot_prefers_live_buffer(self) -> None:
        user, _, meeting, _ = _build_owned_meeting()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting
        db.execute.return_value = result
        db.commit = AsyncMock()
        engine, engine_session = _build_engine_for_meeting(
            meeting,
            transcript="Live transcript text",
        )

        service = LiveSessionService(db=db, engine=engine, provider=MagicMock())
        response = await service.get_transcript_snapshot(meeting.id, user)

        assert response["source"] == "live_buffer"
        assert response["transcript"] == "Live transcript text"
        assert response["engine_session_id"] == engine_session.session_id


class TestLiveSessionRoutes:
    @pytest.mark.asyncio
    async def test_activate_route_passes_through_to_service(self) -> None:
        from app.api.routes.live import activate_live_session

        meeting_id = uuid4()
        service = MagicMock()
        service.activate_for_meeting = AsyncMock(
            return_value={
                "meeting_id": meeting_id,
                "meeting_status": "active",
                "platform": "zoom",
                "meeting_link": "https://zoom.us/j/123456789",
                "engine_session_id": "session-123",
                "provider_bot_id": "bot-123",
                "session_status": "listening",
                "is_active": True,
                "is_muted": False,
                "stop_requested": False,
                "websocket_path": "/api/ws/session-123",
                "transcript_length": 0,
                "last_instruction_at": None,
                "last_transcript_at": None,
                "provider_last_error": None,
                "created_at": _now(),
                "updated_at": _now(),
                "ended_at": None,
            }
        )
        current_user = SimpleNamespace(id=uuid4())

        response = await activate_live_session(
            meeting_id=meeting_id,
            current_user=current_user,
            service=service,
        )

        service.activate_for_meeting.assert_awaited_once_with(meeting_id, current_user)
        assert response["engine_session_id"] == "session-123"
