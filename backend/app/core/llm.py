"""Claude API client.

Provides a single-model interface to Claude Haiku 4.5 for all LLM
operations: meeting Q&A, summarization, and system prompt generation.

Phase 3 implementation.
"""

from __future__ import annotations

from app.config import get_settings

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - depends on local optional install
    anthropic = None

_DEFAULT_SYSTEM_PROMPT = (
    "You are Synth, an intelligent meeting assistant. You have access to "
    "the meeting transcript and any uploaded documents. Answer questions "
    "accurately and concisely based on the provided context. If the context "
    "does not contain enough information to answer, say so honestly rather "
    "than guessing."
)


class LLMClient:
    """Client for the Anthropic Claude API.

    Uses Claude Haiku 4.5 for all queries — fast, cheap, and sufficient
    for real-time meeting Q&A.

    Attributes:
        api_key: Anthropic API key.
        model: Model identifier.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        """Initialize the Claude API client.

        Args:
            model: Model ID to use for all queries.
        """
        self.settings = get_settings()
        self.api_key = self.settings.anthropic_api_key
        self.model = model
        self.client = None
        self._async_client = None

        if anthropic is None or not self.api_key:
            return

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)

    def query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        """Send a question to Claude with assembled context.

        Args:
            context: Assembled context string from the context manager,
                including transcript, RAG results, and document excerpts.
            question: The user's question extracted after wake word detection.
            system_prompt: Optional override for the default system prompt.

        Returns:
            The model's response text.
        """
        if self.client is None:
            raise RuntimeError(
                "Anthropic SDK or API key is not configured for synchronous queries."
            )

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

        user_content = (
            f"Context:\n{context}\n\n"
            f"Question:\n{question}"
        )

        response = self.client.messages.create(
            model=self.model,
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

        Args:
            context: Assembled context string from the context manager.
            question: The user's question text.
            system_prompt: Optional override for the default system prompt.

        Returns:
            The model's response text.
        """
        if self._async_client is None:
            raise RuntimeError(
                "Anthropic SDK or API key is not configured for asynchronous queries."
            )

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

        user_content = (
            f"Context:\n{context}\n\n"
            f"Question:\n{question}"
        )

        response = await self._async_client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=prompt,
            messages=[
                {"role": "user", "content": user_content},
            ],
        )

        return response.content[0].text

    async def async_query_stream(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ):
        """Stream a response from Claude, yielding complete sentences.

        Yields:
            Complete sentences as they are generated.
        """
        if self._async_client is None:
            raise RuntimeError("Anthropic SDK or API key is not configured.")

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_content = f"Context:\n{context}\n\nQuestion:\n{question}"

        buffer = ""
        async with self._async_client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=prompt,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            async for text in stream.text_stream:
                buffer += text
                # Yield on sentence boundaries
                while True:
                    # Find end of sentence
                    best = -1
                    for sep in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
                        idx = buffer.find(sep)
                        if idx != -1 and (best == -1 or idx < best):
                            best = idx + len(sep)
                    if best == -1:
                        break
                    sentence = buffer[:best].strip()
                    buffer = buffer[best:]
                    if sentence:
                        yield sentence

        # Yield remaining text
        if buffer.strip():
            yield buffer.strip()

    def generate_system_prompt(self, description: str) -> str:
        """Generate a system prompt from an agent description.

        Args:
            description: The agent's natural language description provided
                by the user during agent creation.

        Returns:
            A formatted system prompt string for use in Claude API calls.
        """
        return (
            f"You are a specialized meeting assistant with the following "
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
