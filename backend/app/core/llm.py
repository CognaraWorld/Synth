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
from collections.abc import Awaitable, Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

from app.config import get_settings

logger = logging.getLogger(__name__)

_GEMINI_SYNC_WORKER_DRAIN_TIMEOUT_SECONDS = 2.0
_GEMINI_SYNC_WORKER_MAX_WORKERS = 4
_GEMINI_SYNC_ORPHAN_THRESHOLD = 3
_LLM_RETRY_ATTEMPTS = 1
_LLM_RETRY_BASE_DELAY_SECONDS = 0.25
_LLM_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_LLM_RETRYABLE_ERROR_TOKENS = (
    "timeout",
    "temporar",
    "transient",
    "rate limit",
    "resource exhausted",
    "unavailable",
    "overload",
    "service unavailable",
    "deadline exceeded",
    "connection reset",
    "gateway timeout",
)
T = TypeVar("T")

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


def _is_retryable_llm_error(exc: Exception) -> bool:
    """Return True for transient provider failures worth retrying once."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return True

    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(exc, "code", None)
    try:
        if int(status_code) in _LLM_RETRYABLE_STATUS_CODES:
            return True
    except (TypeError, ValueError):
        pass

    message_parts = [exc.__class__.__name__, str(exc)]
    if getattr(exc, "message", None):
        message_parts.append(str(getattr(exc, "message")))
    haystack = " ".join(part for part in message_parts if part).lower()
    return any(token in haystack for token in _LLM_RETRYABLE_ERROR_TOKENS)


class LLMClient:
    """Hybrid LLM client: Gemini Flash (fast) with Claude Haiku (fallback).

    Attributes:
        gemini_client: Google GenAI client for fast Q&A.
        claude_client: Anthropic client for fallback and heavy tasks.
    """

    def __init__(self, claude_model: str = "claude-haiku-4-5-20251001") -> None:
        self.settings = get_settings()
        self.claude_model = claude_model
        self._gemini_stream_executor: ThreadPoolExecutor | None = None
        self._gemini_stream_state_lock = threading.Lock()
        self._gemini_stream_orphans = 0

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

    def _get_gemini_stream_executor(self) -> ThreadPoolExecutor:
        """Create the sync Gemini bridge executor on demand."""
        executor = self._gemini_stream_executor
        if executor is not None:
            return executor
        with self._gemini_stream_state_lock:
            executor = self._gemini_stream_executor
            if executor is None:
                executor = ThreadPoolExecutor(
                    max_workers=_GEMINI_SYNC_WORKER_MAX_WORKERS,
                    thread_name_prefix="gemini-sync-stream",
                )
                self._gemini_stream_executor = executor
        return executor

    def _should_refuse_gemini_sync_stream(self) -> bool:
        """Return True when too many blocked Gemini workers are already pinned."""
        with self._gemini_stream_state_lock:
            orphan_count = self._gemini_stream_orphans
        if orphan_count >= _GEMINI_SYNC_ORPHAN_THRESHOLD:
            logger.warning(
                "Gemini sync bridge disabled: %d orphaned workers still pinned",
                orphan_count,
            )
            return True
        return False

    def _retry_sync_llm_call(self, operation: str, call: Callable[[], T]) -> T:
        """Retry a synchronous LLM call once for transient failures."""
        for attempt in range(_LLM_RETRY_ATTEMPTS + 1):
            try:
                return call()
            except Exception as exc:
                if attempt >= _LLM_RETRY_ATTEMPTS or not _is_retryable_llm_error(exc):
                    raise
                delay = _LLM_RETRY_BASE_DELAY_SECONDS * (attempt + 1)
                logger.warning(
                    "%s failed transiently; retrying in %.2fs (%d/%d): %s",
                    operation,
                    delay,
                    attempt + 1,
                    _LLM_RETRY_ATTEMPTS + 1,
                    exc,
                )
                time.sleep(delay)
        raise RuntimeError(f"{operation} retry loop exhausted unexpectedly")

    async def _retry_async_llm_call(
        self,
        operation: str,
        call: Callable[[], Awaitable[T]],
    ) -> T:
        """Retry an async LLM call once for transient failures."""
        for attempt in range(_LLM_RETRY_ATTEMPTS + 1):
            try:
                return await call()
            except Exception as exc:
                if attempt >= _LLM_RETRY_ATTEMPTS or not _is_retryable_llm_error(exc):
                    raise
                delay = _LLM_RETRY_BASE_DELAY_SECONDS * (attempt + 1)
                logger.warning(
                    "%s failed transiently; retrying in %.2fs (%d/%d): %s",
                    operation,
                    delay,
                    attempt + 1,
                    _LLM_RETRY_ATTEMPTS + 1,
                    exc,
                )
                await asyncio.sleep(delay)
        raise RuntimeError(f"{operation} retry loop exhausted unexpectedly")

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
        # Prompt order is optimized for Gemini implicit prompt caching:
        # stable template + stable-prefix context first; dynamic question
        # and speaker instruction last. ContextManager.assemble_context
        # already places stable sections before the LIVE CONTEXT marker.
        user_content = (
            f"Answer the question directly. Do NOT repeat or summarize the question. "
            f"Keep it concise and conversational — you are speaking aloud in a meeting, not writing an essay. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}\n\n"
            f"--- QUESTION ---\n"
            f"A meeting participant just asked:\n"
            f"\"{question}\"\n"
            f"{speaker_instruction}"
        )

        # Try Gemini first
        if self.gemini_client:
            try:
                start = time.time()
                response = self._retry_sync_llm_call(
                    "Gemini query",
                    lambda: self.gemini_client.models.generate_content(
                        model=self._gemini_model,
                        contents=user_content,
                        config={
                            "system_instruction": prompt,
                            "max_output_tokens": 1024,
                            "temperature": 0.7,
                        },
                    ),
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
        return self._retry_sync_llm_call(
            "Claude fallback query",
            lambda: self._claude_query(context, question, system_prompt),
        )

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
        # See query(): stable template + context first; question + speaker
        # instruction last so Gemini can cache the stable prefix.
        user_content = (
            f"Answer the question directly. Do NOT repeat or summarize the question. "
            f"Keep it concise and conversational — you are speaking aloud in a meeting, not writing an essay. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}\n\n"
            f"--- QUESTION ---\n"
            f"A meeting participant just asked:\n"
            f"\"{question}\"\n"
            f"{speaker_instruction}"
        )

        # Try Gemini first — native async when available, executor fallback
        if self.gemini_client:
            try:
                start = time.time()
                if self._gemini_async_client:
                    response = await self._retry_async_llm_call(
                        "Gemini async query",
                        lambda: asyncio.wait_for(
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
                        ),
                    )
                else:
                    loop = asyncio.get_running_loop()
                    response = await self._retry_async_llm_call(
                        "Gemini async query",
                        lambda: asyncio.wait_for(
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
                        ),
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
        return await self._retry_async_llm_call(
            "Claude fallback query",
            lambda: self._claude_async_query(context, question, system_prompt),
        )

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
        # Keep prompt shape consistent with the Gemini path: static template
        # + context first, question last. Aligns with cache-friendly layout.
        user_content = (
            f"Answer the question directly. Do NOT repeat, narrate, or summarize the question. "
            f"Do NOT say who asked it. Just give the answer. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}\n\n"
            f"--- QUESTION ---\n"
            f"A meeting participant just asked:\n"
            f"\"{question}\""
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
        # See _claude_query(): context-first layout mirrors the Gemini path.
        user_content = (
            f"Answer the question directly. Do NOT repeat, narrate, or summarize the question. "
            f"Do NOT say who asked it. Just give the answer. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}\n\n"
            f"--- QUESTION ---\n"
            f"A meeting participant just asked:\n"
            f"\"{question}\""
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
        # Streaming path — MUST match async_query framing exactly. Using a
        # weaker "Context:" header on Flash Lite causes the model to treat
        # the context as ambient prose and refuse ("I can't read the
        # document") even when the document summary is right there. Keep
        # the stronger "meeting context you can reference" framing.
        user_content = (
            f"Answer the question directly. Do NOT repeat or summarize the question. "
            f"Keep it concise and conversational — you are speaking aloud in a meeting, not writing an essay. "
            f"Combine information from ALL available sources — documents, web search results, "
            f"meeting conversation, and your own knowledge — to give the most complete answer.\n\n"
            f"Here is the meeting context you can reference:\n{context}\n\n"
            f"--- QUESTION ---\n"
            f"A meeting participant just asked:\n"
            f"\"{question}\"\n"
            f"{speaker_instruction}"
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
                    logger.debug(
                        "Gemini async stream emitted no sentences (cancelled or empty response)",
                    )
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
                    logger.debug(
                        "Gemini sync stream emitted no sentences (cancelled or empty response)",
                    )
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
        """Stream sentences from Gemini using the async client (true async I/O).

        google-genai's async client returns a coroutine that resolves to an
        async iterator — the coroutine must be awaited before ``async for``,
        otherwise we fall through to the executor-based sync bridge and
        pay ~50-200 ms of extra latency per streaming call.
        """
        if not self._gemini_async_client:
            return
        stream = await self._gemini_async_client.models.generate_content_stream(
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
        if self._should_refuse_gemini_sync_stream():
            raise RuntimeError("Gemini sync bridge unavailable while orphaned workers recover")

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        stream_error: list[Exception] = []
        stop_worker = threading.Event()
        worker_done = threading.Event()
        worker_marked_orphan = False

        def _mark_worker_orphan(reason: str) -> None:
            nonlocal worker_marked_orphan
            if worker_done.is_set():
                return
            with self._gemini_stream_state_lock:
                if worker_done.is_set() or worker_marked_orphan:
                    return
                worker_marked_orphan = True
                self._gemini_stream_orphans += 1
                orphan_count = self._gemini_stream_orphans
            logger.warning(
                "Gemini sync worker still blocked after %s; orphan count=%d",
                reason,
                orphan_count,
            )

        def _run_gemini_stream() -> None:
            nonlocal worker_marked_orphan
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
                with self._gemini_stream_state_lock:
                    if worker_marked_orphan and self._gemini_stream_orphans > 0:
                        self._gemini_stream_orphans -= 1
                        orphan_count = self._gemini_stream_orphans
                        worker_marked_orphan = False
                        logger.info(
                            "Gemini sync worker recovered; orphan count=%d",
                            orphan_count,
                        )
                loop.call_soon_threadsafe(queue.put_nowait, None)
                worker_done.set()

        executor = self._get_gemini_stream_executor()
        worker_future: Future[None] = executor.submit(_run_gemini_stream)
        task = asyncio.wrap_future(worker_future)

        async def _drain_worker_after_stop(reason: str) -> None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=_GEMINI_SYNC_WORKER_DRAIN_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                if worker_future.cancel():
                    logger.warning(
                        "Gemini sync worker was still queued after %s; cancelled before start",
                        reason,
                    )
                    return
                _mark_worker_orphan(reason)
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
            logger.warning(
                "Multi-turn Claude query failed: %s, falling back to single-turn",
                exc,
            )
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
