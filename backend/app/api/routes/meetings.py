import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.routes.auth import get_current_user
from app.models.database import Agent, Meeting, MeetingSummary, User, get_db
from app.models.schemas import MeetingCreate, MeetingDetailResponse, MeetingResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])


def detect_platform(meeting_link: str) -> str:
    """Auto-detect meeting platform from URL."""
    link = meeting_link.lower()
    if "zoom.us" in link or "zoom.com" in link:
        return "zoom"
    elif "teams.microsoft.com" in link or "teams.live.com" in link:
        return "teams"
    elif "meet.google.com" in link:
        return "meet"
    raise HTTPException(
        status_code=400,
        detail="Unsupported meeting platform. Provide a Zoom, Teams, or Google Meet link.",
    )


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
    )
    db.add(meeting)

    # Deduct credit
    current_user.credits -= 1

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
    # TODO Phase 6: Stop bot via Recall.ai
    # TODO Phase 7: Trigger summary generation

    await db.commit()
    await db.refresh(meeting)
    return meeting
