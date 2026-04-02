"""System prompt builder.

Constructs system prompts for the LLM based on the agent's operating
mode (general or custom). General mode uses a pre-defined expert
meeting participant prompt. Custom mode generates a tailored prompt
from the user's agent description.

Phase 3 implementation.
"""

from __future__ import annotations


def build_general_prompt() -> str:
    """Build the default system prompt for general-mode agents.

    Creates a comprehensive system prompt that instructs the LLM to
    act as a knowledgeable meeting participant who can answer questions,
    provide context, and assist with meeting discussions.

    Returns:
        The formatted system prompt string for general-mode operation.
    """
    # TODO: Return a well-crafted default system prompt
    # TODO: Include instructions for meeting behavior, tone, and capabilities
    raise NotImplementedError("Phase 3 implementation")


def build_custom_prompt(description: str) -> str:
    """Build a tailored system prompt from an agent description.

    Generates a system prompt that incorporates the user's custom
    description, creating a specialized persona for the meeting bot.

    Args:
        description: The user-provided agent description that defines
            the bot's role, expertise area, and behavioral guidelines.

    Returns:
        A formatted system prompt string tailored to the description.
    """
    # TODO: Combine base meeting behavior instructions with custom description
    # TODO: Ensure the prompt maintains safety guardrails
    raise NotImplementedError("Phase 3 implementation")
