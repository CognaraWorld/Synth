import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.config import get_settings
from app.models.database import Agent, Document, Meeting, User, get_db
from app.models.schemas import AgentCreate, AgentResponse, AgentUpdate
from app.utils.storage import is_managed_path
from app.utils.bot_profiles import (
    build_system_prompt,
    get_effective_primary_agent,
    get_persona_voice_label,
    mark_primary_agent,
)
from app.utils.prompt_builder import resolve_persona_id

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(
        select(func.count(Agent.id)).where(Agent.user_id == current_user.id)
    )
    if (count_result.scalar() or 0) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum of 10 agents per user reached",
        )

    has_primary = await get_effective_primary_agent(db, current_user.id) is not None
    persona_id = resolve_persona_id(agent_data.mode, agent_data.persona_id)
    mode = "general"

    agent = Agent(
        user_id=current_user.id,
        name=agent_data.name,
        description=agent_data.description,
        system_prompt=build_system_prompt(mode, agent_data.description, persona_id),
        mode=mode,
        persona_id=persona_id,
        voice=get_persona_voice_label(persona_id),
        response_mode=agent_data.response_mode,
        is_primary=not has_primary,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/", response_model=list[AgentResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.user_id == current_user.id).order_by(Agent.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    update_data: AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    payload = update_data.model_dump(exclude_unset=True, exclude_none=True)
    persona_inputs_changed = "mode" in payload or "persona_id" in payload
    if persona_inputs_changed:
        candidate_mode = payload.get("mode", agent.mode)
        candidate_persona = payload.get("persona_id", agent.persona_id)
        resolved_persona = resolve_persona_id(candidate_mode, candidate_persona)
        payload["mode"] = "general"
        payload["persona_id"] = resolved_persona

    next_persona = payload.get("persona_id", agent.persona_id)
    payload["voice"] = get_persona_voice_label(next_persona)

    if "system_prompt" not in payload and ("description" in payload or persona_inputs_changed):
        next_description = payload.get("description", agent.description)
        next_mode = payload.get("mode", agent.mode)
        payload["system_prompt"] = build_system_prompt(next_mode, next_description, next_persona)

    for field, value in payload.items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger = logging.getLogger(__name__)
    settings = get_settings()

    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 1. Clean up uploaded document files from disk
    doc_result = await db.execute(
        select(Document).where(Document.agent_id == agent_id)
    )
    for doc in doc_result.scalars().all():
        if is_managed_path(Path(settings.upload_dir), doc.file_path):
            file_path = Path(doc.file_path)
            if file_path.exists():
                file_path.unlink()

    # 2. Clean up ChromaDB embeddings for this agent
    try:
        from app.api.routes.documents import _get_rag_pipeline, _rag_pipelines
        rag = _get_rag_pipeline(str(agent_id))
        if rag:
            rag.clear()
            # Remove from cache so it's not reused
            _rag_pipelines.pop(str(agent_id), None)
            logger.info("Cleared ChromaDB collection for agent %s", agent_id)
    except Exception as exc:
        logger.warning("Failed to clear ChromaDB for agent %s: %s", agent_id, exc)

    # 3. Delete agent (cascades to documents + meetings via ORM)
    was_primary = agent.is_primary
    await db.delete(agent)
    await db.flush()

    # 4. Reassign primary if needed
    if was_primary:
        replacement_result = await db.execute(
            select(Agent)
            .where(Agent.user_id == current_user.id)
            .order_by(Agent.created_at.desc())
        )
        replacement = replacement_result.scalars().first()
        if replacement:
            await mark_primary_agent(db, current_user.id, replacement)

    await db.commit()
    logger.info("Agent %s deleted with all associated data", agent_id)
