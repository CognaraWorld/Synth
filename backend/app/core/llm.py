"""LLM client with Gemini Flash (fast) and Claude Haiku (fallback).

Gemini 2.5 Flash is the primary model for meeting Q&A — ~150ms response time.
Claude Haiku 4.5 is the fallback for when Gemini is unavailable, and is used
directly for heavy tasks like meeting summaries and document analysis.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable

from app.config import get_settings

logger = logging.getLogger(__name__)

_GEMINI_SYNC_WORKER_DRAIN_TIMEOUT_SECONDS = 0.2

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


def _first_name_or_empty(speaker: str) -> str:
    """Return the speaker's first token, tolerating blank/whitespace names."""
    cleaned = (speaker or "").strip()
    if not cleaned:
        return ""
    return cleaned.split()[0]


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
        self._gemini_async_client = None
        self._gemini_model = "gemini-2.5-flash-lite"
        if genai and self.settings.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.settings.gemini_api_key)
            try:
                self._gemini_async_client = genai.Client(
                    api_key=self.settings.gemini_api_key,
                ).aio
            except Exception:
                self._gemini_async_client = None
            logger.info("Gemini 2.5 Flash Lite configured as primary LLM")

    # ------------------------------------------------------------------
    # Primary query — tries Gemini first, falls back to Claude
    # ------------------------------------------------------------------

    def query(
        self,
        context: str,
        question: str,
        system_prompt: str | None = None,
        speaker: str = "",
    ) -> str:
        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        speaker_instruction = ""
        first_name = _first_name_or_empty(speaker)
        if first_name:
            speaker_instruction = (
                f"{first_name} asked this question. You may address them by name naturally "
                f"(e.g. 'Great question {first_name},' or 'So {first_name},'). "
                f"Don't force their name into every sentence — use it once or twice at most. "
            )
        user_content = (
            f"A meeting participant just asked you this question:\n"
            f"\"{question}\"\n\n"
            f"{speaker_instruction}"
            f"Answer the question directly. Do NOT repeat or summarize the question. "
            f"Keep it concise and conversational — you are speaking aloud in a meeting, not writing an essay. "
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
        speaker: str = "",
    ) -> str:
        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        speaker_instruction = ""
        first_name = _first_name_or_empty(speaker)
        if first_name:
            speaker_instruction = (
                f"{first_name} asked this question. You may address them by name naturally "
                f"(e.g. 'Great question {first_name},' or 'So {first_name},'). "
                f"Don't force their name into every sentence — use it once or twice at most. "
            )
        user_content = (
            f"A meeting participant just asked you this question:\n"
            f"\"{question}\"\n\n"
            f"{speaker_instruction}"
            f"Answer the question directly. Do NOT repeat or summarize the question. "
            f"Keep it concise and conversational — you are speaking aloud in a meeting, not writing an essay. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}"
        )

        # Try Gemini first — native async when available, executor fallback
        if self.gemini_client:
            try:
                start = time.time()
                if self._gemini_async_client:
                    response = await asyncio.wait_for(
                        self._gemini_async_client.models.generate_content(
                            model=self._gemini_model,
                            contents=user_content,
                            config={
                                "system_instruction": prompt,
                                "max_output_tokens": 1024,
                                "temperature": 0.7,
                            },
                        ),
                        timeout=30.0,
                    )
                else:
                    loop = asyncio.get_running_loop()
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
        speaker: str = "",
        should_cancel: Callable[[], bool] | None = None,
    ):
        """Stream a response yielding complete sentences.

        Tries Gemini streaming first (lower latency), falls back to
        Claude streaming. Each yielded chunk is a full sentence suitable
        for immediate TTS synthesis.

        Args:
            should_cancel: If set, called frequently; when it returns True,
                the provider stream is stopped cooperatively (best-effort).
        """
        prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        speaker_instruction = ""
        first_name = _first_name_or_empty(speaker)
        if first_name:
            speaker_instruction = (
                f"{first_name} asked this question. You may address them by name naturally. "
            )
        user_content = (
            f"A meeting participant just asked you this question:\n"
            f"\"{question}\"\n\n"
            f"{speaker_instruction}"
            f"Answer the question directly. Do NOT repeat or summarize the question. "
            f"Keep it concise and conversational — you are speaking aloud in a meeting. "
            f"Combine information from ALL available sources.\n\n"
            f"Context:\n{context}"
        )

        # Try Gemini native async streaming first (no executor bridge)
        if self._gemini_async_client:
            try:
                start = time.time()
                yielded = False
                async for sentence in self._gemini_stream_native_async(
                    prompt, user_content, should_cancel=should_cancel,
                ):
                    yielded = True
                    yield sentence
                if should_cancel and should_cancel() and not yielded:
                    logger.debug("Gemini async stream cancelled before sentence emission")
                    return
                if yielded:
                    logger.info(
                        "Gemini async stream completed in %.0fms",
                        (time.time() - start) * 1000,
                    )
                    return
            except Exception as exc:
                logger.warning("Gemini async stream failed, trying sync bridge: %s", exc)

        # Sync Gemini client streaming via executor queue (fallback)
        if self.gemini_client:
            try:
                start = time.time()
                yielded = False
                async for sentence in self._gemini_stream(
                    prompt, user_content, should_cancel=should_cancel,
                ):
                    yielded = True
                    yield sentence
                if should_cancel and should_cancel() and not yielded:
                    logger.debug("Gemini sync stream cancelled before sentence emission")
                    return
                if yielded:
                    logger.info("Gemini stream completed in %.0fms", (time.time() - start) * 1000)
                    return
            except Exception as exc:
                logger.warning("Gemini stream failed, falling back to Claude: %s", exc)

        # Fallback to Claude streaming
        if self._claude_async is None:
            yield "I'm having trouble processing right now. Please try again."
            return

        buffer = ""
        async with self._claude_async.messages.stream(
            model=self.claude_model,
            max_tokens=4096,
            system=prompt,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            cancelled = False
            async for text in stream.text_stream:
                if should_cancel and should_cancel():
                    logger.debug("Claude stream cancelled by caller")
                    cancelled = True
                    break
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

        if not cancelled and buffer.strip():
            yield buffer.strip()

    async def _gemini_stream_native_async(
        self,
        system_prompt: str,
        user_content: str,
        should_cancel: Callable[[], bool] | None = None,
    ):
        """Stream sentences from Gemini using the async client (true async I/O)."""
        if not self._gemini_async_client:
            return
        stream = self._gemini_async_client.models.generate_content_stream(
            model=self._gemini_model,
            contents=user_content,
            config={
                "system_instruction": system_prompt,
                "max_output_tokens": 1024,
                "temperature": 0.7,
            },
        )
        buffer = ""
        cancelled = False
        async for chunk in stream:
            if should_cancel and should_cancel():
                logger.debug("Gemini async stream cancelled by caller")
                cancelled = True
                break
            piece = getattr(chunk, "text", None) or ""
            if not piece:
                continue
            buffer += piece
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
        if not cancelled and buffer.strip():
            yield buffer.strip()

    async def _gemini_stream(
        self,
        system_prompt: str,
        user_content: str,
        should_cancel: Callable[[], bool] | None = None,
    ):
        """Stream sentences from Gemini, yielding complete sentences.

        Bridges the sync Gemini SDK to async via a thread executor and
        an asyncio.Queue. Sentinel errors are propagated after draining
        any partial content so callers get whatever was generated.

        When *should_cancel* is set, the blocking iterator in the worker
        thread stops pulling from Gemini as soon as the flag is set.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        stream_error: list[Exception] = []
        stop_worker = threading.Event()

        def _run_gemini_stream() -> None:
            try:
                response = self.gemini_client.models.generate_content_stream(
                    model=self._gemini_model,
                    contents=user_content,
                    config={
                        "system_instruction": system_prompt,
                        "max_output_tokens": 1024,
                        "temperature": 0.7,
                    },
                )
                for chunk in response:
                    if stop_worker.is_set():
                        break
                    if chunk.text:
                        loop.call_soon_threadsafe(queue.put_nowait, chunk.text)
            except Exception as exc:
                stream_error.append(exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        task = loop.run_in_executor(None, _run_gemini_stream)

        async def _drain_worker_after_stop(reason: str) -> None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=_GEMINI_SYNC_WORKER_DRAIN_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.debug("Gemini sync worker still blocked after %s", reason)
            except Exception:
                pass

        def _schedule_worker_drain(reason: str) -> None:
            asyncio.create_task(_drain_worker_after_stop(reason))

        buffer = ""
        cancelled = False
        try:
            while True:
                try:
                    token = await asyncio.wait_for(queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    if should_cancel and should_cancel():
                        stop_worker.set()
                        cancelled = True
                        break
                    continue
                if token is None:
                    break
                buffer += token
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
        except asyncio.CancelledError:
            stop_worker.set()
            _schedule_worker_drain("caller cancellation")
            raise

        if not cancelled and buffer.strip():
            yield buffer.strip()

        if cancelled:
            await _drain_worker_after_stop("cancellation")
            return

        await task

        if stream_error:
            raise stream_error[0]

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
