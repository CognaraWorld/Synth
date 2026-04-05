"""Backend control plane for live meeting sessions and operator commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.websocket import get_engine
from app.config import get_settings
from app.core.bot_engine import BotEngine
from app.meeting.recall_client import RecallClient
from app.models.database import Agent, LiveSession, Meeting, OperatorInstruction, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_active_status(session_status: str) -> bool:
    return session_status in {"joining", "listening", "responding", "active"}


def _map_engine_state_to_meeting_status(session_status: str) -> str:
    if session_status in {"listening", "responding"}:
        return "active"
    return session_status


class LiveSessionServiceError(Exception):
    """Raised when a live-session operation cannot be completed."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class ProviderActionResult:
    provider_status: str
    detail: str | None = None


class MeetingControlProvider(Protocol):
    """Provider-specific execution hooks for live meeting controls."""

    def is_configured(self) -> bool:
        """Return whether provider credentials are configured."""

    async def mute(self, bot_id: str | None) -> ProviderActionResult:
        """Apply mute to the provider session when possible."""

    async def unmute(self, bot_id: str | None) -> ProviderActionResult:
        """Apply unmute to the provider session when possible."""

    async def stop_speaking(self, bot_id: str | None) -> ProviderActionResult:
        """Interrupt provider-side playback when supported."""

    async def leave(self, bot_id: str | None) -> ProviderActionResult:
        """Remove the bot from the provider-side meeting session."""


class RecallMeetingControlProvider:
    """Best-effort control adapter for Recall.ai-backed meetings."""

    def __init__(
        self,
        api_key: str | None = None,
        client: RecallClient | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.recall_api_key
        self._client = client

    def is_configured(self) -> bool:
        return bool((self.api_key or "").strip())

    async def _get_client(self) -> RecallClient:
        if self._client is None:
            self._client = RecallClient(api_key=self.api_key)
        return self._client

    async def mute(self, bot_id: str | None) -> ProviderActionResult:
        if not self.is_configured():
            return ProviderActionResult(
                provider_status="not_configured",
                detail="Recall.ai credentials are not configured yet.",
            )
        if not bot_id:
            return ProviderActionResult(
                provider_status="missing_bot",
                detail="No provider bot id is available for this meeting.",
            )
        client = await self._get_client()
        await client.mute(bot_id)
        return ProviderActionResult(provider_status="applied")

    async def unmute(self, bot_id: str | None) -> ProviderActionResult:
        if not self.is_configured():
            return ProviderActionResult(
                provider_status="not_configured",
                detail="Recall.ai credentials are not configured yet.",
            )
        if not bot_id:
            return ProviderActionResult(
                provider_status="missing_bot",
                detail="No provider bot id is available for this meeting.",
            )
        client = await self._get_client()
        await client.unmute(bot_id)
        return ProviderActionResult(provider_status="applied")

    async def stop_speaking(self, bot_id: str | None) -> ProviderActionResult:
        if not self.is_configured():
            return ProviderActionResult(
                provider_status="not_configured",
                detail="Recall.ai credentials are not configured yet.",
            )
        if not bot_id:
            return ProviderActionResult(
                provider_status="missing_bot",
                detail="No provider bot id is available for this meeting.",
            )
        return ProviderActionResult(
            provider_status="pending_integration",
            detail=(
                "Provider-side playback interruption is not wired yet. "
                "The backend records the stop request and drops any unsent response audio."
            ),
        )

    async def leave(self, bot_id: str | None) -> ProviderActionResult:
        if not self.is_configured():
            return ProviderActionResult(
                provider_status="not_configured",
                detail="Recall.ai credentials are not configured yet.",
            )
        if not bot_id:
            return ProviderActionResult(
                provider_status="missing_bot",
                detail="No provider bot id is available for this meeting.",
            )
        client = await self._get_client()
        await client.stop_bot(bot_id)
        return ProviderActionResult(provider_status="applied")


class LiveSessionService:
    """Coordinates persisted live session state with the in-memory bot engine."""

    def __init__(
        self,
        db: AsyncSession,
        engine: BotEngine | None = None,
        provider: MeetingControlProvider | None = None,
    ) -> None:
        self.db = db
        self.engine = engine or get_engine()
        self.provider = provider or RecallMeetingControlProvider()

    async def list_for_user(self, current_user: User) -> list[dict]:
        result = await self.db.execute(
            select(LiveSession)
            .join(Meeting)
            .options(joinedload(LiveSession.meeting))
            .where(Meeting.user_id == current_user.id)
            .order_by(LiveSession.updated_at.desc())
        )
        sessions = result.scalars().all()
        synced_sessions: list[LiveSession] = []
        for live_session in sessions:
            synced_sessions.append(
                self._sync_live_session_record(live_session.meeting, live_session)
            )
        await self.db.flush()
        await self.db.commit()
        return [self._serialize_live_session(live_session) for live_session in synced_sessions]

    async def activate_for_meeting(self, meeting_id: UUID, current_user: User) -> dict:
        meeting = await self._get_owned_meeting(
            meeting_id,
            current_user.id,
            include_agent=True,
            include_live_session=True,
        )
        if meeting.status in {"ended", "failed"}:
            raise LiveSessionServiceError(409, "Only pending or active meetings can be activated.")

        live_session = meeting.live_session or self._create_live_session(meeting)
        engine_session = self._find_engine_session(meeting, live_session)
        if engine_session is None:
            if not self.provider.is_configured():
                raise LiveSessionServiceError(
                    503,
                    "Recall.ai is not configured for live meeting activation yet.",
                )
            session_id = await self.engine.join_meeting(
                meeting.meeting_link,
                self._build_agent_config(meeting.agent),
                meeting_id=str(meeting.id),
            )
            engine_session = self.engine.sessions.get(session_id)

        synced = self._sync_live_session_record(meeting, live_session, engine_session)
        if meeting.started_at is None:
            meeting.started_at = _utcnow()
        meeting.status = "active"

        await self.db.commit()
        return self._serialize_live_session(synced)

    async def get_for_meeting(self, meeting_id: UUID, current_user: User) -> dict:
        meeting = await self._get_owned_meeting(
            meeting_id,
            current_user.id,
            include_live_session=True,
        )
        live_session = meeting.live_session
        engine_session = self._find_engine_session(meeting, live_session)
        if live_session is None and engine_session is None:
            raise LiveSessionServiceError(404, "Live session not found for this meeting.")

        synced = self._sync_live_session_record(meeting, live_session, engine_session)
        await self.db.commit()
        return self._serialize_live_session(synced)

    async def get_transcript_snapshot(self, meeting_id: UUID, current_user: User) -> dict:
        meeting = await self._get_owned_meeting(
            meeting_id,
            current_user.id,
            include_live_session=True,
        )
        live_session = meeting.live_session
        engine_session = self._find_engine_session(meeting, live_session)

        transcript = ""
        source = "none"
        session_status = meeting.status
        engine_session_id = live_session.engine_session_id if live_session else None
        updated_at = _utcnow()

        if engine_session is not None:
            transcript = self.engine.get_transcript_text(engine_session.session_id)
            source = "live_buffer"
            session_status = engine_session.get_state()
            engine_session_id = engine_session.session_id
            if transcript:
                synced = self._sync_live_session_record(meeting, live_session, engine_session)
                synced.last_transcript_at = updated_at
                live_session = synced
        elif meeting.transcript:
            transcript = meeting.transcript
            source = "meeting_record"
            if live_session and live_session.last_transcript_at:
                updated_at = live_session.last_transcript_at

        await self.db.commit()
        return {
            "meeting_id": meeting.id,
            "engine_session_id": engine_session_id,
            "session_status": session_status,
            "source": source,
            "transcript": transcript,
            "updated_at": updated_at,
        }

    async def list_instructions(self, meeting_id: UUID, current_user: User) -> list[dict]:
        await self._get_owned_meeting(meeting_id, current_user.id)
        result = await self.db.execute(
            select(OperatorInstruction)
            .where(OperatorInstruction.meeting_id == meeting_id)
            .order_by(OperatorInstruction.created_at.asc())
        )
        return [
            self._serialize_instruction(instruction)
            for instruction in result.scalars().all()
        ]

    async def submit_instruction(
        self,
        meeting_id: UUID,
        current_user: User,
        instruction_text: str,
    ) -> dict:
        meeting = await self._get_owned_meeting(
            meeting_id,
            current_user.id,
            include_live_session=True,
        )
        live_session = meeting.live_session or self._create_live_session(meeting)
        engine_session = self._find_engine_session(meeting, live_session)
        if engine_session is None and not _is_active_status(meeting.status):
            raise LiveSessionServiceError(409, "Live session is not active for this meeting.")

        instruction = OperatorInstruction(
            user_id=current_user.id,
            meeting_id=meeting.id,
            live_session=live_session,
            instruction_text=instruction_text,
            delivery_status="queued",
        )
        self.db.add(instruction)

        if engine_session is not None:
            self.engine.submit_operator_instruction(engine_session.session_id, instruction_text)
            instruction.delivery_status = "applied"
            instruction.applied_at = _utcnow()
            live_session.last_instruction_at = instruction.applied_at
            self._sync_live_session_record(meeting, live_session, engine_session)

        await self.db.commit()
        await self.db.refresh(instruction)
        return self._serialize_instruction(instruction)

    async def set_mute_state(
        self,
        meeting_id: UUID,
        current_user: User,
        muted: bool,
    ) -> dict:
        meeting = await self._get_owned_meeting(
            meeting_id,
            current_user.id,
            include_live_session=True,
        )
        live_session = meeting.live_session or self._create_live_session(meeting)
        engine_session = self._find_engine_session(meeting, live_session)
        if engine_session is None and not live_session.provider_bot_id and not meeting.bot_id:
            raise LiveSessionServiceError(409, "Live session is not active for this meeting.")

        if engine_session is not None:
            self.engine.set_session_muted(engine_session.session_id, muted)

        provider_bot_id = self._get_provider_bot_id(meeting, live_session, engine_session)
        provider_result = (
            await self.provider.mute(provider_bot_id)
            if muted
            else await self.provider.unmute(provider_bot_id)
        )

        synced = self._sync_live_session_record(meeting, live_session, engine_session)
        synced.is_muted = muted
        synced.provider_last_error = provider_result.detail
        await self.db.commit()
        return {
            "meeting_id": meeting.id,
            "session_status": synced.session_status,
            "provider_status": provider_result.provider_status,
            "detail": provider_result.detail,
            "is_muted": muted,
            "stop_requested": synced.stop_requested,
            "ended_at": synced.ended_at,
        }

    async def request_stop_speaking(self, meeting_id: UUID, current_user: User) -> dict:
        meeting = await self._get_owned_meeting(
            meeting_id,
            current_user.id,
            include_live_session=True,
        )
        live_session = meeting.live_session or self._create_live_session(meeting)
        engine_session = self._find_engine_session(meeting, live_session)
        if engine_session is None and not live_session.provider_bot_id and not meeting.bot_id:
            raise LiveSessionServiceError(409, "Live session is not active for this meeting.")

        if engine_session is not None:
            self.engine.request_stop_speaking(engine_session.session_id)

        provider_result = await self.provider.stop_speaking(
            self._get_provider_bot_id(meeting, live_session, engine_session)
        )

        synced = self._sync_live_session_record(meeting, live_session, engine_session)
        synced.stop_requested = True
        synced.provider_last_error = provider_result.detail
        await self.db.commit()
        return {
            "meeting_id": meeting.id,
            "session_status": synced.session_status,
            "provider_status": provider_result.provider_status,
            "detail": provider_result.detail,
            "is_muted": synced.is_muted,
            "stop_requested": True,
            "ended_at": synced.ended_at,
        }

    async def leave_meeting(self, meeting_id: UUID, current_user: User) -> dict:
        meeting = await self._get_owned_meeting(
            meeting_id,
            current_user.id,
            include_live_session=True,
        )
        live_session = meeting.live_session or self._create_live_session(meeting)
        engine_session = self._find_engine_session(meeting, live_session)

        provider_status = "skipped"
        detail = None
        ended_at = _utcnow()

        if engine_session is not None:
            result = await self.engine.stop_meeting(engine_session.session_id)
            meeting.status = "ended"
            meeting.ended_at = ended_at
            if result.get("transcript"):
                meeting.transcript = result["transcript"]
            live_session.engine_session_id = engine_session.session_id
            live_session.provider_bot_id = engine_session.bot_id or live_session.provider_bot_id
            live_session.session_status = "ended"
            live_session.stop_requested = False
            live_session.ended_at = ended_at
            provider_status = "engine_stop"
        else:
            provider_result = await self.provider.leave(
                self._get_provider_bot_id(meeting, live_session, engine_session)
            )
            provider_status = provider_result.provider_status
            detail = provider_result.detail
            live_session.provider_last_error = detail
            if provider_status == "applied":
                meeting.status = "ended"
                meeting.ended_at = ended_at
                live_session.session_status = "ended"
                live_session.ended_at = ended_at
                live_session.stop_requested = False

        await self.db.commit()
        return {
            "meeting_id": meeting.id,
            "session_status": live_session.session_status,
            "provider_status": provider_status,
            "detail": detail,
            "is_muted": live_session.is_muted,
            "stop_requested": live_session.stop_requested,
            "ended_at": live_session.ended_at,
        }

    async def _get_owned_meeting(
        self,
        meeting_id: UUID,
        user_id: UUID,
        *,
        include_agent: bool = False,
        include_live_session: bool = False,
    ) -> Meeting:
        options = []
        if include_agent:
            options.append(joinedload(Meeting.agent))
        if include_live_session:
            options.append(joinedload(Meeting.live_session))

        query = select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == user_id)
        if options:
            query = query.options(*options)

        result = await self.db.execute(query)
        meeting = result.scalar_one_or_none()
        if meeting is None:
            raise LiveSessionServiceError(404, "Meeting not found.")
        return meeting

    def _create_live_session(self, meeting: Meeting) -> LiveSession:
        live_session = LiveSession(
            meeting_id=meeting.id,
            session_status=meeting.status,
        )
        meeting.live_session = live_session
        self.db.add(live_session)
        return live_session

    def _find_engine_session(
        self,
        meeting: Meeting,
        live_session: LiveSession | None,
    ):
        if live_session and live_session.engine_session_id:
            session = self.engine.sessions.get(live_session.engine_session_id)
            if session is not None:
                return session

        session = self.engine.find_session_for_meeting(str(meeting.id))
        if session is not None:
            return session

        for candidate in self.engine.sessions.values():
            if candidate.meeting_id == meeting.meeting_link:
                return candidate
        return None

    def _sync_live_session_record(
        self,
        meeting: Meeting,
        live_session: LiveSession | None,
        engine_session=None,
    ) -> LiveSession:
        live_session = live_session or self._create_live_session(meeting)
        engine_session = engine_session or self._find_engine_session(meeting, live_session)

        if engine_session is not None:
            session_status = engine_session.get_state()
            live_session.engine_session_id = engine_session.session_id
            live_session.provider_bot_id = engine_session.bot_id or live_session.provider_bot_id
            live_session.session_status = session_status
            live_session.is_muted = engine_session.operator_muted
            live_session.stop_requested = engine_session.output_stop_requested
            live_session.last_instruction_at = engine_session.last_instruction_at
            meeting.status = _map_engine_state_to_meeting_status(session_status)
            if engine_session.bot_id:
                meeting.bot_id = engine_session.bot_id

            transcript_text = self.engine.get_transcript_text(engine_session.session_id)
            if transcript_text:
                live_session.last_transcript_at = _utcnow()
                if session_status in {"ended", "failed"}:
                    meeting.transcript = transcript_text

            if session_status in {"ended", "failed"}:
                live_session.ended_at = live_session.ended_at or _utcnow()
                meeting.ended_at = meeting.ended_at or live_session.ended_at

        return live_session

    def _serialize_live_session(self, live_session: LiveSession) -> dict:
        meeting = live_session.meeting
        transcript_length = 0
        if live_session.engine_session_id and live_session.engine_session_id in self.engine.sessions:
            transcript_length = len(self.engine.get_transcript_text(live_session.engine_session_id))
        elif meeting.transcript:
            transcript_length = len(meeting.transcript)

        return {
            "meeting_id": meeting.id,
            "meeting_status": meeting.status,
            "platform": str(meeting.platform),
            "meeting_link": meeting.meeting_link,
            "engine_session_id": live_session.engine_session_id,
            "provider_bot_id": live_session.provider_bot_id or meeting.bot_id,
            "session_status": live_session.session_status,
            "is_active": _is_active_status(live_session.session_status),
            "is_muted": live_session.is_muted,
            "stop_requested": live_session.stop_requested,
            "websocket_path": (
                f"/api/ws/{live_session.engine_session_id}"
                if live_session.engine_session_id
                else None
            ),
            "transcript_length": transcript_length,
            "last_instruction_at": live_session.last_instruction_at,
            "last_transcript_at": live_session.last_transcript_at,
            "provider_last_error": live_session.provider_last_error,
            "created_at": live_session.created_at,
            "updated_at": live_session.updated_at,
            "ended_at": live_session.ended_at,
        }

    def _serialize_instruction(self, instruction: OperatorInstruction) -> dict:
        return {
            "id": instruction.id,
            "meeting_id": instruction.meeting_id,
            "live_session_id": instruction.live_session_id,
            "instruction": instruction.instruction_text,
            "delivery_status": instruction.delivery_status,
            "delivery_error": instruction.delivery_error,
            "created_at": instruction.created_at,
            "applied_at": instruction.applied_at,
        }

    def _build_agent_config(self, agent: Agent) -> dict[str, str]:
        return {
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "description": agent.description,
            "mode": agent.mode,
            "persona_id": getattr(agent, "persona_id", "general"),
            "voice": agent.voice,
            "system_prompt": agent.system_prompt,
        }

    def _get_provider_bot_id(
        self,
        meeting: Meeting,
        live_session: LiveSession,
        engine_session,
    ) -> str | None:
        if engine_session is not None and engine_session.bot_id:
            return engine_session.bot_id
        return live_session.provider_bot_id or meeting.bot_id
