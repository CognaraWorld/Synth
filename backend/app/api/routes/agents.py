from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.models.database import Agent, User, get_db
from app.models.schemas import AgentCreate, AgentResponse, AgentUpdate
from app.utils.bot_profiles import build_system_prompt

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.user_id == current_user.id, Agent.is_primary.is_(True))
    )
    has_primary = result.scalar_one_or_none() is not None

    agent = Agent(
        user_id=current_user.id,
        name=agent_data.name,
        description=agent_data.description,
        system_prompt=build_system_prompt(agent_data.mode, agent_data.description),
        mode=agent_data.mode,
        voice=agent_data.voice,
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

    payload = update_data.model_dump(exclude_unset=True)
    if "system_prompt" not in payload and ("description" in payload or "mode" in payload):
        next_description = payload.get("description", agent.description)
        next_mode = payload.get("mode", agent.mode)
        payload["system_prompt"] = build_system_prompt(next_mode, next_description)

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
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    was_primary = agent.is_primary
    await db.delete(agent)
    await db.flush()

    if was_primary:
        replacement_result = await db.execute(
            select(Agent)
            .where(Agent.user_id == current_user.id)
            .order_by(Agent.created_at.desc())
        )
        replacement = replacement_result.scalars().first()
        if replacement:
            replacement.is_primary = True

    await db.commit()
