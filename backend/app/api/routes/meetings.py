from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.routes.auth import get_current_user
from app.models.credit_transaction import CreditTransaction
from app.config import get_settings
from app.meeting.reporting import calculate_minutes_used, finalize_meeting_artifacts_for_meeting_id
from app.models.database import Agent, Meeting, User, get_db
from app.models.schemas import MeetingCreate, MeetingDetailResponse, MeetingResponse
from app.utils.meeting_links import detect_meeting_platform

router = APIRouter(prefix="/meetings", tags=["meetings"])
settings = get_settings()


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

    # Verify agent belongs to user
    result = await db.execute(
        select(Agent).where(Agent.id == meeting_data.agent_id, Agent.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    platform = detect_platform(meeting_data.meeting_link)

    meeting = Meeting(
        user_id=current_user.id,
        agent_id=meeting_data.agent_id,
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
        .options(joinedload(Meeting.summary))
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
    meeting.ended_at = datetime.now(timezone.utc)
    if meeting.duration_minutes is None:
        meeting.duration_minutes = calculate_minutes_used(meeting)

    # TODO Phase 6: Stop bot via Recall.ai
    await finalize_meeting_artifacts(
        db=db,
        meeting=meeting,
        current_user=current_user,
        settings=settings,
    )

    await db.commit()
    await db.refresh(meeting)
    return meeting
