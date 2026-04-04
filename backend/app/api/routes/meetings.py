from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

import logging

from app.api.routes.auth import get_current_user
from app.api.routes.webhook import get_bot_engine, set_bot_engine
from app.config import get_settings
from app.meeting.recall_client import RecallClient, RecallClientError
from app.models.database import Agent, Meeting, MeetingSummary, User, get_db
from app.models.schemas import MeetingCreate, MeetingDetailResponse, MeetingResponse
from app.utils.meeting_links import detect_meeting_platform

logger = logging.getLogger(__name__)

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

    # Build webhook URL for real-time transcription
    settings = get_settings()
    webhook_url = None
    if settings.webhook_base_url:
        webhook_url = f"{settings.webhook_base_url.rstrip('/')}/api/webhook/recall"
        logger.info("Webhook URL: %s", webhook_url)

    # Deploy Recall.ai bot into the meeting
    recall = RecallClient()
    try:
        bot_id = await recall.create_bot(
            meeting_url=meeting_data.meeting_link,
            bot_name=agent.name or "Synth",
            webhook_url=webhook_url,
        )
        meeting.bot_id = bot_id
        meeting.status = "active"
        await db.commit()
        await db.refresh(meeting)
        logger.info("Bot %s joined meeting %s", bot_id, meeting.id)

        # Initialize BotEngine session so webhook has a target
        engine = get_bot_engine()
        agent_config = {
            "agent_id": str(agent.id),
            "agent_name": agent.name or "Synth",
            "mode": agent.mode or "general",
            "description": agent.description or "",
        }

        # Register session directly (bot already deployed via RecallClient above)
        from app.context.manager import ContextManager
        from app.meeting.session import MeetingSession, SessionState

        session = MeetingSession(
            meeting_id=meeting_data.meeting_link,
            agent_config=agent_config,
        )
        session.bot_id = bot_id

        # Build system prompt
        from app.utils.prompt_builder import build_custom_prompt, build_general_prompt
        if agent_config["mode"] == "custom" and agent_config["description"]:
            session.agent_config["system_prompt"] = build_custom_prompt(agent_config["description"])
        else:
            session.agent_config["system_prompt"] = build_general_prompt()

        # Wire up rolling summary with LLM
        session.context_manager.rolling_summary.set_llm_client(engine._llm_client)

        # Wire up RAG pipeline for document search
        from app.api.routes.documents import _get_rag_pipeline
        rag = _get_rag_pipeline(str(agent.id))
        session.context_manager.set_rag_pipeline(rag)

        # Load document summaries for the agent
        try:
            from app.models.database import Document
            doc_result = await db.execute(
                select(Document).where(
                    Document.agent_id == agent.id,
                    Document.parsed.is_(True),
                    Document.doc_summary.isnot(None),
                )
            )
            documents = doc_result.scalars().all()
            for doc in documents:
                session.context_manager.add_document_summary(doc.filename, doc.doc_summary)
            if documents:
                logger.info("Loaded %d doc summaries for agent %s", len(documents), agent.id)
        except Exception as exc:
            logger.warning("Failed to load doc summaries: %s", exc)

        # Set session states and register
        session.transition(SessionState.JOINING)
        session.transition(SessionState.LISTENING)
        engine.sessions[session.session_id] = session
        engine._sessions_by_bot_id[bot_id] = session.session_id

        logger.info("BotEngine session %s ready for bot %s", session.session_id, bot_id)

    except RecallClientError as exc:
        logger.error("Failed to deploy bot for meeting %s: %s", meeting.id, exc)
        meeting.status = "failed"
        current_user.credits += 1  # refund credit
        await db.commit()
        raise HTTPException(status_code=502, detail="Failed to deploy meeting bot. Credit refunded.")
    finally:
        await recall.close()

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

    # Stop via BotEngine (flushes RAG, cleans up session, stops Recall bot)
    engine = get_bot_engine()
    session_id = engine._sessions_by_bot_id.get(meeting.bot_id) if meeting.bot_id else None
    if session_id:
        try:
            await engine.stop_meeting(session_id)
        except Exception as exc:
            logger.warning("BotEngine stop failed: %s", exc)
    elif meeting.bot_id:
        # No session — stop bot directly
        recall = RecallClient()
        try:
            await recall.stop_bot(meeting.bot_id)
        except RecallClientError as exc:
            logger.warning("Failed to stop bot %s: %s", meeting.bot_id, exc)
        finally:
            await recall.close()

    meeting.status = "ended"

    await db.commit()
    await db.refresh(meeting)
    return meeting
