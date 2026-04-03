from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.models.database import Agent, User, get_db
from app.models.schemas import BotProfileResponse, BotProfileUpsert
from app.utils.bot_profiles import build_system_prompt, get_effective_primary_agent, mark_primary_agent

router = APIRouter(prefix="/bot", tags=["bot"])


@router.get("/profile", response_model=BotProfileResponse)
async def get_bot_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await get_effective_primary_agent(db, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Bot profile not found")
    return agent


@router.put("/profile", response_model=BotProfileResponse)
async def upsert_bot_profile(
    profile_data: BotProfileUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await get_effective_primary_agent(db, current_user.id)
    system_prompt = profile_data.system_prompt or build_system_prompt(
        profile_data.mode,
        profile_data.description,
    )

    if agent is None:
        agent = Agent(
            user_id=current_user.id,
            name=profile_data.name,
            description=profile_data.description,
            system_prompt=system_prompt,
            mode=profile_data.mode,
            voice=profile_data.voice,
            response_mode=profile_data.response_mode,
            is_primary=True,
        )
        db.add(agent)
    else:
        agent.name = profile_data.name
        agent.description = profile_data.description
        agent.system_prompt = system_prompt
        agent.mode = profile_data.mode
        agent.voice = profile_data.voice
        agent.response_mode = profile_data.response_mode
        agent.is_primary = True

    await db.flush()
    await mark_primary_agent(db, current_user.id, agent)
    await db.commit()
    await db.refresh(agent)
    return agent
