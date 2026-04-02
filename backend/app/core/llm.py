"""Claude API client with hybrid complexity routing.

Provides intelligent routing between Haiku (fast/cheap) and Sonnet
(powerful/expensive) based on question complexity classification.
Handles system prompt generation for both general and custom agent modes.

Phase 3 implementation.
"""

from __future__ import annotations

from app.config import get_settings


class LLMClient:
    """Client for the Anthropic Claude API with hybrid model routing.

    Routes simple factual questions to Haiku for speed and cost savings,
    while directing complex analytical questions to Sonnet for quality.

    Attributes:
        api_key: Anthropic API key.
        haiku_model: Model identifier for the fast/cheap tier.
        sonnet_model: Model identifier for the powerful tier.
    """

    def __init__(
        self,
        haiku_model: str = "claude-3-5-haiku-20241022",
        sonnet_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """Initialize the Claude API client.

        Args:
            haiku_model: Model ID for simple queries (fast, low cost).
            sonnet_model: Model ID for complex queries (high quality).
        """
        self.settings = get_settings()
        self.api_key = self.settings.anthropic_api_key
        self.haiku_model = haiku_model
        self.sonnet_model = sonnet_model
        # TODO: Initialize Anthropic client with API key
        raise NotImplementedError("Phase 3 implementation")

    def query(self, context: str, question: str) -> str:
        """Send a question to Claude with assembled context.

        Automatically classifies the question complexity and routes
        to the appropriate model tier.

        Args:
            context: Assembled context string from the context manager,
                including transcript, RAG results, and document excerpts.
            question: The user's question extracted after wake word detection.

        Returns:
            The model's response text.
        """
        # TODO: Classify complexity, select model, call Anthropic API
        # TODO: Include system prompt, context, and question in the message
        raise NotImplementedError("Phase 3 implementation")

    def classify_complexity(self, question: str) -> str:
        """Classify question complexity for model routing.

        Uses lightweight heuristics and/or a fast model call to determine
        whether a question needs the more capable (and expensive) model.

        Args:
            question: The user's question text.

        Returns:
            "simple" for factual/lookup questions routed to Haiku,
            "complex" for analytical/multi-step questions routed to Sonnet.
        """
        # TODO: Implement keyword heuristics + optional Haiku classification
        raise NotImplementedError("Phase 3 implementation")

    def generate_system_prompt(self, description: str) -> str:
        """Generate a system prompt from an agent description.

        Creates a tailored system prompt based on the agent's description,
        incorporating role-specific instructions and behavioral guidelines.

        Args:
            description: The agent's natural language description provided
                by the user during agent creation.

        Returns:
            A formatted system prompt string for use in Claude API calls.
        """
        # TODO: Use prompt template to generate system prompt from description
        raise NotImplementedError("Phase 3 implementation")
