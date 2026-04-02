from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.models.database import Agent, User, get_db
from app.models.schemas import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])

GENERAL_SYSTEM_PROMPT = """You are Synth, a helpful AI meeting assistant. You are participating in a live meeting as a voice participant.

Guidelines:
- Listen carefully to the conversation and provide helpful, concise answers when asked
- Only speak when addressed by name ("Hey Synth" or "Synth")
- Keep responses brief and meeting-appropriate (30 seconds or less when spoken)
- If you need to search the web for information, do so and provide accurate answers
- If you're unsure about something, say so honestly
- Be professional, friendly, and concise
- Reference uploaded documents when relevant to the discussion"""


async def generate_custom_prompt(description: str) -> str:
    """Generate a tailored system prompt from user description.
    In Phase 5, this will use Claude Haiku to generate the prompt.
    For now, use a template approach."""
    return f"""You are Synth, an AI meeting assistant with the following role and expertise:

{description}

Guidelines:
- Stay in character for the entire meeting based on the role described above
- Listen carefully to the conversation and provide helpful, concise answers when asked
- Only speak when addressed by name ("Hey Synth" or "Synth")
- Keep responses brief and meeting-appropriate (30 seconds or less when spoken)
- Draw on your described expertise to provide relevant insights
- If you need to search the web for information, do so and provide accurate answers
- If asked about uploaded documents, reference them specifically
- Be professional, friendly, and concise"""


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if agent_data.mode == "custom":
        system_prompt = await generate_custom_prompt(agent_data.description)
    else:
        system_prompt = GENERAL_SYSTEM_PROMPT

    agent = Agent(
        user_id=current_user.id,
        name=agent_data.name,
        description=agent_data.description,
        system_prompt=system_prompt,
        mode=agent_data.mode,
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

    for field, value in update_data.model_dump(exclude_unset=True).items():
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

    await db.delete(agent)
    await db.commit()
