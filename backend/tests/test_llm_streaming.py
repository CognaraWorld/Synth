"""Regression tests for LLM streaming cancellation behavior."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from types import SimpleNamespace

import pytest


class _PendingExecutor:
    def __init__(self, future: Future[None]) -> None:
        self.future = future

    def submit(self, _func):
        return self.future


def test_query_retries_transient_gemini_failure_before_succeeding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import llm as llm_module
    from app.core.llm import LLMClient

    class _TransientGeminiError(RuntimeError):
        status_code = 503

    client = LLMClient()
    attempts = 0
    sleep_calls: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    def generate_content(**_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _TransientGeminiError("service unavailable")
        return SimpleNamespace(text="Gemini answer")

    monkeypatch.setattr(llm_module.time, "sleep", fake_sleep)
    client.gemini_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content),
    )

    def fail_claude(*_args, **_kwargs):
        raise AssertionError(
            "Claude fallback should not run when Gemini succeeds on retry",
        )

    client._claude_query = fail_claude

    result = client.query(context="ctx", question="question")

    assert result == "Gemini answer"
    assert attempts == 2
    assert sleep_calls == [0.25]


@pytest.mark.asyncio
async def test_async_query_retries_transient_claude_failure_before_succeeding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import llm as llm_module
    from app.core.llm import LLMClient

    class _TransientClaudeError(RuntimeError):
        status_code = 429

    client = LLMClient()
    attempts = 0
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    async def create(**_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _TransientClaudeError("rate limited")
        return SimpleNamespace(content=[SimpleNamespace(text="Claude answer")])

    monkeypatch.setattr(llm_module.asyncio, "sleep", fake_sleep)
    client.gemini_client = None
    client._claude_async = SimpleNamespace(messages=SimpleNamespace(create=create))

    result = await client.async_query(context="ctx", question="question")

    assert result == "Claude answer"
    assert attempts == 2
    assert sleep_calls == [0.25]


@pytest.mark.asyncio
async def test_async_query_stream_cancelled_async_gemini_does_not_fallback() -> None:
    from app.core.llm import LLMClient

    client = LLMClient()
    client._gemini_async_client = object()
    client.gemini_client = object()

    async def _cancelled_native(*args, **kwargs):
        if False:
            yield ""
        return

    async def _fail_sync_fallback(*args, **kwargs):
        raise AssertionError("sync Gemini fallback should not run after cancellation")
        if False:
            yield ""

    client._gemini_stream_native_async = _cancelled_native
    client._gemini_stream = _fail_sync_fallback

    chunks = []
    async for chunk in client.async_query_stream(
        context="ctx",
        question="question",
        should_cancel=lambda: True,
    ):
        chunks.append(chunk)

    assert chunks == []


@pytest.mark.asyncio
async def test_async_query_stream_cancelled_sync_gemini_does_not_fallback_to_claude() -> None:
    from app.core.llm import LLMClient

    client = LLMClient()
    client._gemini_async_client = None
    client.gemini_client = object()
    client._claude_async = None

    async def _cancelled_sync(*args, **kwargs):
        if False:
            yield ""
        return

    client._gemini_stream = _cancelled_sync

    chunks = []
    async for chunk in client.async_query_stream(
        context="ctx",
        question="question",
        should_cancel=lambda: True,
    ):
        chunks.append(chunk)

    assert chunks == []


@pytest.mark.asyncio
async def test_gemini_sync_stream_cancel_returns_promptly_when_worker_hangs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import llm as llm_module
    from app.core.llm import LLMClient

    client = LLMClient()
    client.gemini_client = object()

    pending_worker: Future[None] = Future()

    monkeypatch.setattr(llm_module, "_GEMINI_SYNC_WORKER_DRAIN_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(
        client,
        "_get_gemini_stream_executor",
        lambda: _PendingExecutor(pending_worker),
    )

    chunks = []

    async def _collect() -> None:
        async for chunk in client._gemini_stream(
            "prompt",
            "content",
            should_cancel=lambda: True,
        ):
            chunks.append(chunk)

    await asyncio.wait_for(_collect(), timeout=0.5)
    assert chunks == []


@pytest.mark.asyncio
async def test_gemini_sync_stream_sets_stop_signal_when_generator_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import llm as llm_module
    from app.core.llm import LLMClient

    client = LLMClient()
    client.gemini_client = object()

    pending_worker: Future[None] = Future()

    class SpyEvent:
        instances: list["SpyEvent"] = []

        def __init__(self) -> None:
            self.was_set = False
            SpyEvent.instances.append(self)

        def is_set(self) -> bool:
            return self.was_set

        def set(self) -> None:
            self.was_set = True

    monkeypatch.setattr(llm_module, "_GEMINI_SYNC_WORKER_DRAIN_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(llm_module.threading, "Event", SpyEvent)
    monkeypatch.setattr(
        client,
        "_get_gemini_stream_executor",
        lambda: _PendingExecutor(pending_worker),
    )

    async def _consume() -> None:
        async for _ in client._gemini_stream("prompt", "content"):
            pass

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert SpyEvent.instances
    assert SpyEvent.instances[0].was_set is True
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_gemini_sync_stream_marks_and_clears_orphaned_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import llm as llm_module
    from app.core.llm import LLMClient

    started = threading.Event()
    release_worker = threading.Event()

    class _BlockingModels:
        @staticmethod
        def generate_content_stream(**_kwargs):
            started.set()
            release_worker.wait(timeout=1.0)
            return []

    client = LLMClient()
    client.gemini_client = SimpleNamespace(models=_BlockingModels())

    monkeypatch.setattr(llm_module, "_GEMINI_SYNC_WORKER_DRAIN_TIMEOUT_SECONDS", 0.05)

    async def _collect() -> None:
        async for _ in client._gemini_stream(
            "prompt",
            "content",
            should_cancel=lambda: started.is_set(),
        ):
            pass

    await asyncio.wait_for(_collect(), timeout=0.5)
    assert client._gemini_stream_orphans == 1

    release_worker.set()
    await asyncio.sleep(0.1)
    assert client._gemini_stream_orphans == 0
