"""Tests for persona-aware prompt generation."""

from __future__ import annotations

import pytest

from app.utils.prompt_builder import (
    build_prompt_for_mode,
    resolve_persona_id,
    resolve_persona_tts_voice,
    resolve_persona_voice,
)


def test_resolve_persona_id_defaults_from_mode() -> None:
    assert resolve_persona_id("general", None) == "general"
    assert resolve_persona_id("custom", None) == "general"
    assert resolve_persona_id("general", "unknown") == "general"


@pytest.mark.parametrize(
    ("persona_id", "expected_snippet"),
    [
        ("general", "inclusive and highly capable assistant"),
        ("strategist", "recommendation -> why -> key tradeoff"),
        ("analyst", "signals, metrics, assumptions, conclusion"),
        ("challenger", "stress-test proposals and expose blind spots"),
        ("facilitator", "Keep conversation moving toward alignment"),
    ],
)
def test_curated_persona_prompts_have_distinct_instructions(
    persona_id: str,
    expected_snippet: str,
) -> None:
    prompt = build_prompt_for_mode("general", "Roadmap planning context", persona_id)
    assert expected_snippet in prompt
    assert "Roadmap planning context" in prompt


def test_custom_persona_id_falls_back_to_general_prompt() -> None:
    prompt = build_prompt_for_mode("custom", "ignored", "custom")
    assert "inclusive and highly capable assistant" in prompt


@pytest.mark.parametrize(
    ("persona_id", "voice_label", "tts_voice"),
    [
        ("general", "female", "af_heart"),
        ("strategist", "male", "am_adam"),
        ("analyst", "female", "af_heart"),
        ("challenger", "male", "am_michael"),
        ("facilitator", "female", "af_heart"),
    ],
)
def test_persona_voice_mapping(persona_id: str, voice_label: str, tts_voice: str) -> None:
    assert resolve_persona_voice(persona_id) == voice_label
    assert resolve_persona_tts_voice(persona_id) == tts_voice
