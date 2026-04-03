"""Helpers for dashboard bot profiles and per-meeting settings."""

from __future__ import annotations

from app.utils.prompt_builder import build_prompt_for_mode


DEFAULT_BOT_NAME = "Synth"
DEFAULT_BOT_VOICE = "female"
DEFAULT_RESPONSE_MODE = "name_only"


def build_system_prompt(mode: str, description: str) -> str:
    """Build the effective system prompt for a profile or override."""
    return build_prompt_for_mode(mode, description)
