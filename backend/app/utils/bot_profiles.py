"""Helpers for dashboard bot profiles and per-meeting settings."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Agent
from app.utils.prompt_builder import (
    build_prompt_for_mode,
    resolve_persona_id,
    resolve_persona_voice,
    resolve_persona_tts_voice,
)


DEFAULT_BOT_NAME = "Synth"
DEFAULT_BOT_VOICE = "female"
DEFAULT_RESPONSE_MODE = "name_only"
DEFAULT_PERSONA_ID = "general"


def build_system_prompt(mode: str, description: str, persona_id: str | None = None) -> str:
    """Build the effective system prompt for a profile or override."""
    resolved_persona_id = resolve_persona_id(mode, persona_id)
    return build_prompt_for_mode(mode, description, resolved_persona_id)


def get_persona_voice_label(persona_id: str | None) -> str:
    """Return fixed API-facing voice label for persona."""
    return resolve_persona_voice(persona_id)


def get_persona_tts_voice(persona_id: str | None) -> str:
    """Return fixed Kokoro voice id for persona."""
    return resolve_persona_tts_voice(persona_id)


async def get_effective_primary_agent(db: AsyncSession, user_id) -> Agent | None:
    """Return the user's effective primary agent, repairing duplicate primaries if needed."""
    result = await db.execute(
        select(Agent)
        .where(Agent.user_id == user_id)
        .order_by(Agent.is_primary.desc(), Agent.created_at.desc())
    )
    agents = result.scalars().all()
    if not agents:
        return None

    primary_agent = next((agent for agent in agents if agent.is_primary), agents[0])
    for agent in agents:
        agent.is_primary = agent.id == primary_agent.id
    return primary_agent


async def mark_primary_agent(db: AsyncSession, user_id, primary_agent: Agent) -> None:
    """Ensure exactly one agent is primary for the given user."""
    result = await db.execute(select(Agent).where(Agent.user_id == user_id))
    for agent in result.scalars().all():
        agent.is_primary = agent.id == primary_agent.id
