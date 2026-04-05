import math
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

import logging

from app.api.routes.auth import get_current_user
from app.api.routes.webhook import get_bot_engine, set_bot_engine
from app.config import get_settings
from app.meeting.recall_client import RecallClient, RecallClientError
from app.models.database import Agent, Meeting, MeetingOverride, MeetingSummary, User, get_db
from app.models.schemas import (
    MeetingCreate,
    MeetingDetailResponse,
    MeetingOverrideResponse,
    MeetingOverrideUpsert,
    MeetingResponse,
)
from app.utils.bot_profiles import (
    build_system_prompt,
    get_effective_primary_agent,
    get_persona_voice_label,
)
from app.utils.meeting_links import detect_meeting_platform
from app.utils.prompt_builder import resolve_persona_id

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
    # Atomically reserve 5 minutes to prevent overdraw under concurrent requests.
    # The WHERE guard ensures the UPDATE is a no-op when balance is too low.
    reserve_result = await db.execute(
        update(User)
        .where(User.id == current_user.id, User.credits >= 5)
        .values(credits=User.credits - 5)
    )
    if reserve_result.rowcount == 0:
        raise HTTPException(status_code=402, detail="Insufficient minutes balance (minimum 5 required)")

    settings = get_settings()
    if not (settings.gemini_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is required for screenshare capture.",
        )

    agent = None
    if meeting_data.agent_id is None:
        agent = await get_effective_primary_agent(db, current_user.id)
    else:
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
        agent_id=agent.id,
        platform=platform,
        meeting_link=meeting_data.meeting_link,
        status="pending",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        credits_used=0,
    )
    db.add(meeting)

    await db.commit()
    await db.refresh(meeting)

    # Build webhook URL for real-time transcription
    if not (settings.recall_api_key or "").strip():
        logger.info("Recall.ai API key not configured; meeting %s remains pending", meeting.id)
        return meeting

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
            "persona_id": getattr(agent, "persona_id", "general"),
            "description": agent.description or "",
            "system_prompt": agent.system_prompt or "",
            "voice": agent.voice or "female",
        }

        # Register session directly (bot already deployed via RecallClient above)
        from app.context.manager import ContextManager
        from app.meeting.session import MeetingSession, SessionState

        session = MeetingSession(
            meeting_id=meeting_data.meeting_link,
            agent_config=agent_config,
        )
        session.bot_id = bot_id

        # Build system prompt (prefer persisted prompt; fallback for legacy rows)
        persisted_prompt = (agent_config.get("system_prompt") or "").strip()
        if persisted_prompt:
            session.agent_config["system_prompt"] = persisted_prompt
        else:
            session.agent_config["system_prompt"] = build_system_prompt(
                agent_config.get("mode", "general"),
                agent_config.get("description", ""),
                agent_config.get("persona_id"),
            )

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

        # Load past meeting summaries for cross-meeting memory (last 3)
        try:
            past_result = await db.execute(
                select(Meeting)
                .options(joinedload(Meeting.summary))
                .where(
                    Meeting.agent_id == agent.id,
                    Meeting.status == "ended",
                    Meeting.id != meeting.id,
                )
                .order_by(Meeting.created_at.desc())
                .limit(3)
            )
            past_meetings = past_result.unique().scalars().all()
            for pm in past_meetings:
                if pm.summary and pm.summary.content:
                    date_str = pm.created_at.strftime("%Y-%m-%d %H:%M") if pm.created_at else "unknown"
                    session.context_manager.add_past_meeting_summary(date_str, pm.summary.content)
            if past_meetings:
                loaded = sum(1 for pm in past_meetings if pm.summary and pm.summary.content)
                if loaded:
                    logger.info("Loaded %d past meeting summaries for agent %s", loaded, agent.id)
        except Exception as exc:
            logger.warning("Failed to load past meeting summaries: %s", exc)

        # Ensure screenshare capture is wired for meetings created via REST route.
        engine.wire_screen_capture(session)

        # Set session states and register
        session.transition(SessionState.JOINING)
        session.transition(SessionState.LISTENING)
        engine.sessions[session.session_id] = session
        engine._sessions_by_bot_id[bot_id] = session.session_id
        engine._ensure_session_tracking(session.session_id)

        logger.info("BotEngine session %s ready for bot %s", session.session_id, bot_id)

    except RecallClientError as exc:
        logger.error("Failed to deploy bot for meeting %s: %s", meeting.id, exc)
        meeting.status = "failed"
        await db.commit()
        raise HTTPException(status_code=502, detail="Failed to deploy meeting bot.")
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


@router.put("/{meeting_id}/override", response_model=MeetingOverrideResponse)
async def upsert_meeting_override(
    meeting_id: UUID,
    override_data: MeetingOverrideUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.agent), joinedload(Meeting.override))
        .where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status == "active":
        raise HTTPException(
            status_code=409,
            detail="Meeting overrides can only be changed before the meeting is active.",
        )

    meeting_agent = meeting.agent
    if meeting_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    override = meeting.override
    creating_override = override is None
    if override is None:
        override = MeetingOverride(meeting_id=meeting.id)
        db.add(override)

    payload = override_data.model_dump(exclude_unset=True, exclude_none=True)
    persona_inputs_changed = "mode" in payload or "persona_id" in payload
    if persona_inputs_changed:
        candidate_mode = payload.get("mode", override.mode or meeting_agent.mode or "general")
        candidate_persona = payload.get(
            "persona_id",
            override.persona_id or getattr(meeting_agent, "persona_id", "general"),
        )
        resolved_persona = resolve_persona_id(candidate_mode, candidate_persona)
        payload["mode"] = "general"
        payload["persona_id"] = resolved_persona
    elif creating_override:
        payload["mode"] = "general"
        payload["persona_id"] = resolve_persona_id(
            meeting_agent.mode or "general",
            getattr(meeting_agent, "persona_id", "general"),
        )

    next_persona = payload.get(
        "persona_id",
        override.persona_id or getattr(meeting_agent, "persona_id", "general"),
    )
    payload["voice"] = payload.get("voice", override.voice or get_persona_voice_label(next_persona))

    if "system_prompt" not in payload and ("description" in payload or persona_inputs_changed or creating_override):
        next_description = payload.get(
            "description",
            override.description if override.description is not None else meeting_agent.description,
        ) or ""
        next_mode = payload.get("mode", override.mode or meeting_agent.mode or "general")
        next_persona = payload.get(
            "persona_id",
            override.persona_id or getattr(meeting_agent, "persona_id", "general"),
        )
        payload["system_prompt"] = build_system_prompt(next_mode, next_description, next_persona)

    for field, value in payload.items():
        setattr(override, field, value)

    await db.commit()
    await db.refresh(override)
    return override


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

    # Calculate actual minutes used
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if meeting.started_at:
        duration_seconds = (now - meeting.started_at).total_seconds()
        minutes_used = max(1, math.ceil(duration_seconds / 60))  # minimum 1 minute
    else:
        minutes_used = 1

    # Idempotent billing: atomic UPDATE with credits_used = 0 guard prevents
    # double-deduct when both the stop endpoint and the webhook fire.
    bill_result = await db.execute(
        update(Meeting)
        .where(Meeting.id == meeting.id, Meeting.credits_used == 0)
        .values(
            status="ended",
            ended_at=now,
            duration_minutes=minutes_used,
            credits_used=minutes_used,
        )
    )

    if bill_result.rowcount == 1:
        # We won the race -- settle the balance.
        # 5 minutes were reserved at start; refund/charge the difference.
        delta = minutes_used - 5
        await db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(credits=User.credits - delta)
        )
    else:
        # Already billed by webhook -- just ensure status is ended
        meeting.status = "ended"
        if not meeting.ended_at:
            meeting.ended_at = now

    await db.commit()
    await db.refresh(meeting)
    return meeting
