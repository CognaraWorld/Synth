from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.routes.auth import get_current_user
from app.models.credit_transaction import CreditTransaction
from app.models.database import Agent, Meeting, MeetingOverride, MeetingSummary, User, get_db
from app.models.schemas import (
    MeetingCreate,
    MeetingDetailResponse,
    MeetingOverrideResponse,
    MeetingOverrideUpsert,
    MeetingResponse,
)
from app.utils.bot_profiles import build_system_prompt
from app.utils.bot_profiles import get_effective_primary_agent
from app.utils.meeting_links import detect_meeting_platform

router = APIRouter(prefix="/meetings", tags=["meetings"])


def detect_platform(meeting_link: str) -> str:
    """Auto-detect meeting platform from a validated URL."""
    try:
        return detect_meeting_platform(meeting_link)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    meeting_data: MeetingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check credits
    if current_user.credits < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    if meeting_data.agent_id is not None:
        result = await db.execute(
            select(Agent).where(Agent.id == meeting_data.agent_id, Agent.user_id == current_user.id)
        )
        agent = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(Agent)
            .where(Agent.user_id == current_user.id)
            .order_by(Agent.is_primary.desc(), Agent.created_at.desc())
        )
        agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="No bot profile found for this user")

    platform = detect_platform(meeting_data.meeting_link)

    meeting = Meeting(
        user_id=current_user.id,
        agent_id=agent.id,
        platform=platform,
        meeting_link=meeting_data.meeting_link,
        status="pending",
        credits_used=1,
    )
    db.add(meeting)
    await db.flush()

    # Deduct credit
    current_user.credits -= meeting.credits_used
    db.add(
        CreditTransaction(
            user_id=current_user.id,
            meeting_id=meeting.id,
            amount=-meeting.credits_used,
            balance_after=current_user.credits,
            transaction_type="meeting_used",
            description=f"Started {platform} meeting",
        )
    )

    await db.commit()
    await db.refresh(meeting)

    # TODO Phase 6: Trigger bot join via Recall.ai here
    # await bot_engine.join_meeting(meeting)

    return meeting


@router.get("/", response_model=list[MeetingResponse])
async def list_meetings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .where(Meeting.user_id == current_user.id)
        .order_by(Meeting.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
async def get_meeting(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.summary), joinedload(Meeting.override))
        .where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.post("/{meeting_id}/stop", response_model=MeetingResponse)
async def stop_meeting(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status != "active":
        raise HTTPException(status_code=400, detail="Meeting is not active")

    meeting.status = "ended"
    # TODO Phase 6: Stop bot via Recall.ai
    # TODO Phase 7: Trigger summary generation

    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("/{meeting_id}/override", response_model=MeetingOverrideResponse)
async def get_meeting_override(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.override))
        .where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.override:
        raise HTTPException(status_code=404, detail="Meeting override not found")
    return meeting.override


@router.put("/{meeting_id}/override", response_model=MeetingOverrideResponse)
async def upsert_meeting_override(
    meeting_id: UUID,
    override_data: MeetingOverrideUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.override), joinedload(Meeting.agent))
        .where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.status not in {"pending", "joining"}:
        raise HTTPException(
            status_code=409,
            detail="Meeting overrides can only be changed before the meeting is active.",
        )

    override = meeting.override
    if override is None:
        override = MeetingOverride(meeting_id=meeting.id)
        db.add(override)

    payload = override_data.model_dump(exclude_unset=True)
    for field in ("description", "mode", "system_prompt", "voice", "response_mode"):
        if field in payload:
            setattr(override, field, payload[field])

    if "system_prompt" not in payload and ("description" in payload or "mode" in payload):
        if "description" in payload and "mode" not in payload:
            override.mode = "custom"

        effective_mode = override.mode or meeting.agent.mode
        effective_description = override.description or meeting.agent.description
        override.system_prompt = build_system_prompt(effective_mode, effective_description)

    await db.commit()
    await db.refresh(override)
    return override


@router.delete("/{meeting_id}/override", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_override(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.override))
        .where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.override:
        raise HTTPException(status_code=404, detail="Meeting override not found")
    if meeting.status not in {"pending", "joining"}:
        raise HTTPException(
            status_code=409,
            detail="Meeting overrides can only be changed before the meeting is active.",
        )

    await db.delete(meeting.override)
    await db.commit()
