"""System prompt builder.

Constructs system prompts for the LLM based on the agent's operating
mode (general or custom). General mode uses a pre-defined expert
meeting participant prompt. Custom mode generates a tailored prompt
from the user's agent description.

Phase 3 implementation.
"""

from __future__ import annotations

_BEHAVIORAL_GUIDELINES = """\
Behavioral Guidelines:
- Only speak when addressed by name ("Hey Synth" or "Synth").
- Keep responses concise — aim for roughly 30 seconds when spoken aloud.
- Be professional, friendly, and direct.
- If you searched the web for information, cite your sources briefly.
- If you reference uploaded documents, mention which document by name.
- If you are unsure about something, say so honestly rather than speculating.
- Focus on being helpful, not verbose.
- Adapt your tone to match the meeting context (casual standup vs. formal review).
- Never fabricate facts, statistics, or quotes. If the provided context is \
insufficient, acknowledge the gap.
- When multiple interpretations of a question are possible, address the most \
likely one and briefly note the alternative.
- Avoid jargon unless the meeting participants are clearly using it themselves.
- Do not repeat information that was just stated in the meeting unless asked \
to clarify or summarize it."""


def build_general_prompt() -> str:
    """Build the default system prompt for general-mode agents.

    Creates a comprehensive system prompt that instructs the LLM to
    act as a knowledgeable meeting participant who can answer questions,
    provide context, and assist with meeting discussions.

    Returns:
        The formatted system prompt string for general-mode operation.
    """
    return (
        "You are Synth, a meeting participant. You join meetings to help "
        "the team by answering questions, providing information, and "
        "offering insights.\n"
        "\n"
        "Capabilities:\n"
        "- Answer factual questions using the meeting transcript and any "
        "uploaded documents provided as context.\n"
        "- Search the web when a question requires current or real-time "
        "information and present a concise summary with sources.\n"
        "- Read and reference text extracted from screen shares when "
        "available.\n"
        "- Summarize discussion points, action items, or decisions when "
        "asked.\n"
        "\n"
        f"{_BEHAVIORAL_GUIDELINES}"
    )


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
    return (
        "You are Synth, a meeting participant with the following role:\n"
        "\n"
        f"{description}\n"
        "\n"
        f"{_BEHAVIORAL_GUIDELINES}\n"
        "\n"
        "Stay in character as described above for the entire meeting."
    )
