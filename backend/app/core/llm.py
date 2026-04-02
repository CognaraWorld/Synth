"""Claude API client with hybrid complexity routing.

Provides intelligent routing between Haiku (fast/cheap) and Sonnet
(powerful/expensive) based on question complexity classification.
Handles system prompt generation for both general and custom agent modes.

Phase 3 implementation.
"""

from __future__ import annotations

import anthropic

from app.config import get_settings

# Keywords / phrases that signal an analytical or multi-step question.
_COMPLEX_INDICATORS: tuple[str, ...] = (
    "summarize",
    "analyze",
    "compare",
    "explain why",
    "what are the implications",
    "how does this affect",
    "evaluate",
    "contrast",
    "assess",
    "elaborate",
    "break down",
    "what factors",
    "pros and cons",
    "trade-offs",
    "in what ways",
    "critically",
    "synthesize",
    "interpret",
    "what would happen if",
    "how might",
)

_DEFAULT_SYSTEM_PROMPT = (
    "You are Synth, an intelligent AI meeting assistant. You have access to "
    "the meeting transcript and any uploaded documents. Answer questions "
    "accurately and concisely based on the provided context. If the context "
    "does not contain enough information to answer, say so honestly rather "
    "than guessing."
)


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
        haiku_model: str = "claude-haiku-4-5-20251001",
        sonnet_model: str = "claude-sonnet-4-5-20250514",
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
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)

    def query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        """Send a question to Claude with assembled context.

        Automatically classifies the question complexity and routes
        to the appropriate model tier.

        Args:
            context: Assembled context string from the context manager,
                including transcript, RAG results, and document excerpts.
            question: The user's question extracted after wake word detection.
            system_prompt: Optional override for the default system prompt.

        Returns:
            The model's response text.
        """
        complexity = self.classify_complexity(question)
        model = self.sonnet_model if complexity == "complex" else self.haiku_model
        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

        user_content = (
            f"Context:\n{context}\n\n"
            f"Question:\n{question}"
        )

        response = self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=prompt,
            messages=[
                {"role": "user", "content": user_content},
            ],
        )

        return response.content[0].text

    async def async_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        """Send a question to Claude asynchronously.

        Behaves identically to ``query`` but uses the async Anthropic
        client, making it suitable for use inside async request handlers.

        Args:
            context: Assembled context string from the context manager.
            question: The user's question text.
            system_prompt: Optional override for the default system prompt.

        Returns:
            The model's response text.
        """
        complexity = self.classify_complexity(question)
        model = self.sonnet_model if complexity == "complex" else self.haiku_model
        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

        user_content = (
            f"Context:\n{context}\n\n"
            f"Question:\n{question}"
        )

        response = await self._async_client.messages.create(
            model=model,
            max_tokens=4096,
            system=prompt,
            messages=[
                {"role": "user", "content": user_content},
            ],
        )

        return response.content[0].text

    def classify_complexity(self, question: str) -> str:
        """Classify question complexity for model routing.

        Uses lightweight keyword heuristics to determine whether a
        question needs the more capable (and expensive) model. No API
        call is made, keeping classification fast and free.

        Args:
            question: The user's question text.

        Returns:
            "simple" for factual/lookup questions routed to Haiku,
            "complex" for analytical/multi-step questions routed to Sonnet.
        """
        question_lower = question.lower()
        for indicator in _COMPLEX_INDICATORS:
            if indicator in question_lower:
                return "complex"
        return "simple"

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
        return (
            f"You are a specialized AI meeting assistant with the following "
            f"role and expertise:\n\n"
            f"{description}\n\n"
            f"Guidelines:\n"
            f"- Stay in character and respond according to your defined role.\n"
            f"- Base your answers on the provided meeting context and any "
            f"uploaded documents.\n"
            f"- Be concise but thorough. Prioritize accuracy over speculation.\n"
            f"- If the context does not contain enough information to answer "
            f"a question, acknowledge the gap rather than fabricating details.\n"
            f"- When referencing specific parts of the transcript or documents, "
            f"cite them clearly so the user can verify."
        )
