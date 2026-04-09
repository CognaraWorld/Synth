"""LLM client with Gemini Flash (fast) and Claude Haiku (fallback).

Gemini 2.5 Flash is the primary model for meeting Q&A — ~150ms response time.
Claude Haiku 4.5 is the fallback for when Gemini is unavailable, and is used
directly for heavy tasks like meeting summaries and document analysis.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    import anthropic
except ModuleNotFoundError:
    anthropic = None

try:
    from google import genai
except ModuleNotFoundError:
    genai = None

_DEFAULT_SYSTEM_PROMPT = (
    "You are Synth, an intelligent meeting assistant. You have access to "
    "the meeting transcript and any uploaded documents. Answer questions "
    "accurately and concisely based on the provided context. If the context "
    "does not contain enough information to answer, say so honestly rather "
    "than guessing."
)


class LLMClient:
    """Hybrid LLM client: Gemini Flash (fast) with Claude Haiku (fallback).

    Attributes:
        gemini_client: Google GenAI client for fast Q&A.
        claude_client: Anthropic client for fallback and heavy tasks.
    """

    def __init__(self, claude_model: str = "claude-haiku-4-5-20251001") -> None:
        self.settings = get_settings()
        self.claude_model = claude_model

        # Claude setup (fallback + heavy tasks)
        self.claude_client = None
        self._claude_async = None
        if anthropic and self.settings.anthropic_api_key:
            self.claude_client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
            self._claude_async = anthropic.AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        # Gemini setup (primary fast path)
        self.gemini_client = None
        self._gemini_model = "gemini-2.5-flash-lite"
        if genai and self.settings.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.settings.gemini_api_key)
            logger.info("Gemini 2.5 Flash Lite configured as primary LLM")

    # ------------------------------------------------------------------
    # Primary query — tries Gemini first, falls back to Claude
    # ------------------------------------------------------------------

    def query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_content = (
            f"A meeting participant just asked you this question:\n"
            f"\"{question}\"\n\n"
            f"Answer the question directly. Do NOT repeat, narrate, or summarize the question. "
            f"Do NOT say who asked it. Just give the answer. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}"
        )

        # Try Gemini first
        if self.gemini_client:
            try:
                start = time.time()
                response = self.gemini_client.models.generate_content(
                    model=self._gemini_model,
                    contents=user_content,
                    config={
                        "system_instruction": prompt,
                        "max_output_tokens": 1024,
                        "temperature": 0.7,
                    },
                )
                elapsed = time.time() - start
                logger.info("Gemini responded in %.0fms", elapsed * 1000)
                text = response.text
                if not text:
                    raise ValueError("Gemini returned empty/blocked response")
                return text
            except Exception as exc:
                logger.warning("Gemini failed, falling back to Claude: %s", exc)

        # Fallback to Claude
        return self._claude_query(context, question, system_prompt)

    async def async_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_content = (
            f"A meeting participant just asked you this question:\n"
            f"\"{question}\"\n\n"
            f"Answer the question directly. Do NOT repeat, narrate, or summarize the question. "
            f"Do NOT say who asked it. Just give the answer. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}"
        )

        # Try Gemini first (run sync SDK in executor with timeout)
        if self.gemini_client:
            try:
                loop = asyncio.get_running_loop()
                start = time.time()
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.gemini_client.models.generate_content(
                            model=self._gemini_model,
                            contents=user_content,
                            config={
                                "system_instruction": prompt,
                                "max_output_tokens": 1024,
                                "temperature": 0.7,
                            },
                        ),
                    ),
                    timeout=30.0,
                )
                elapsed = time.time() - start
                logger.info("Gemini responded in %.0fms", elapsed * 1000)
                text = response.text
                if not text:
                    raise ValueError("Gemini returned empty/blocked response")
                return text
            except asyncio.TimeoutError:
                logger.warning("Gemini timed out after 30s, falling back to Claude")
            except Exception as exc:
                logger.warning("Gemini failed, falling back to Claude: %s", exc)

        # Fallback to Claude
        return await self._claude_async_query(context, question, system_prompt)

    # ------------------------------------------------------------------
    # Claude-only methods (for summaries, complex tasks, fallback)
    # ------------------------------------------------------------------

    def _claude_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        if self.claude_client is None:
            logger.error("No LLM configured (neither Gemini nor Claude)")
            return "I'm having trouble processing right now. Please try again in a moment."

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_content = (
            f"A meeting participant just asked you this question:\n"
            f"\"{question}\"\n\n"
            f"Answer the question directly. Do NOT repeat, narrate, or summarize the question. "
            f"Do NOT say who asked it. Just give the answer. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}"
        )

        start = time.time()
        response = self.claude_client.messages.create(
            model=self.claude_model,
            max_tokens=4096,
            system=prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        elapsed = time.time() - start
        logger.info("Claude responded in %.0fms", elapsed * 1000)
        if not response.content:
            raise ValueError("Claude returned empty content")
        return response.content[0].text

    async def _claude_async_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        if self._claude_async is None:
            logger.error("No LLM configured (neither Gemini nor Claude)")
            return "I'm having trouble processing right now. Please try again in a moment."

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_content = (
            f"A meeting participant just asked you this question:\n"
            f"\"{question}\"\n\n"
            f"Answer the question directly. Do NOT repeat, narrate, or summarize the question. "
            f"Do NOT say who asked it. Just give the answer. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}"
        )

        start = time.time()
        response = await self._claude_async.messages.create(
            model=self.claude_model,
            max_tokens=4096,
            system=prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        elapsed = time.time() - start
        logger.info("Claude responded in %.0fms", elapsed * 1000)
        if not response.content:
            raise ValueError("Claude returned empty content")
        return response.content[0].text

    def claude_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        """Force Claude for heavy tasks (summaries, document analysis)."""
        return self._claude_query(context, question, system_prompt)

    async def claude_async_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ) -> str:
        """Force Claude async for heavy tasks."""
        return await self._claude_async_query(context, question, system_prompt)

    async def async_query_stream(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
    ):
        """Stream a response from Claude, yielding complete sentences."""
        if self._claude_async is None:
            raise RuntimeError("Claude SDK not configured for streaming.")

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_content = f"Context:\n{context}\n\nQuestion:\n{question}"

        buffer = ""
        async with self._claude_async.messages.stream(
            model=self.claude_model,
            max_tokens=4096,
            system=prompt,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            async for text in stream.text_stream:
                buffer += text
                while True:
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

        if buffer.strip():
            yield buffer.strip()

    async def multi_turn_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
        chat_history: list[dict] | None = None,
    ) -> str:
        """Multi-turn conversation using Claude with full message history."""
        if self._claude_async is None:
            return await self.async_query(context, question, system_prompt)

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        prompt += (
            "\n\nThink through complex questions step by step. "
            "Break them into sub-questions and address each one. "
            "Reference specific parts of the context."
        )

        messages: list[dict[str, str]] = []
        if chat_history:
            for message in chat_history[-10:]:
                messages.append({"role": message["role"], "content": message["content"]})

        user_content = f"Context:\n{context}\n\nQuestion:\n{question}"
        messages.append({"role": "user", "content": user_content})

        try:
            response = await self._claude_async.messages.create(
                model=self.claude_model,
                max_tokens=4096,
                system=prompt,
                messages=messages,
            )
            return response.content[0].text if response.content else ""
        except Exception as exc:
            logger.warning("Multi-turn Claude query failed: %s, falling back to single-turn", exc)
            return await self.async_query(context, question, system_prompt)

    async def tool_use_query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        tool_executor=None,
        max_rounds: int = 3,
    ) -> tuple[str, list[dict]]:
        """Query Claude with tool use. Returns (response_text, tool_calls_made)."""
        if self._claude_async is None or not tools:
            return await self.async_query(context, question, system_prompt), []

        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_content = f"Context:\n{context}\n\nQuestion:\n{question}"
        messages: list[dict] = [{"role": "user", "content": user_content}]
        tool_calls_made: list[dict] = []

        for _ in range(max_rounds):
            try:
                response = await self._claude_async.messages.create(
                    model=self.claude_model,
                    max_tokens=4096,
                    system=prompt,
                    messages=messages,
                    tools=tools,
                )
            except Exception as exc:
                logger.warning("Tool-use Claude query failed: %s", exc)
                return await self.async_query(context, question, system_prompt), []

            if response.stop_reason == "tool_use":
                assistant_content = response.content
                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for block in assistant_content:
                    if getattr(block, "type", None) != "tool_use":
                        continue

                    tool_name = getattr(block, "name", "")
                    tool_input = getattr(block, "input", {}) or {}
                    if tool_executor:
                        result = await tool_executor(tool_name, tool_input)
                    else:
                        result = f"Tool {tool_name} not available"

                    tool_calls_made.append(
                        {
                            "tool_name": tool_name,
                            "input": tool_input,
                            "output_summary": str(result)[:200],
                        }
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": getattr(block, "id", ""),
                            "content": result,
                        }
                    )

                messages.append({"role": "user", "content": tool_results})
                continue

            text_parts = [
                block.text
                for block in response.content
                if getattr(block, "type", None) == "text" and getattr(block, "text", None)
            ]
            return " ".join(text_parts).strip(), tool_calls_made

        return (
            "I wasn't able to complete all the research needed. Please try a more specific question.",
            tool_calls_made,
        )

    def generate_system_prompt(self, description: str) -> str:
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
