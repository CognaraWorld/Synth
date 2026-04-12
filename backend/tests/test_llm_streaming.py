"""Regression tests for LLM streaming cancellation behavior."""

from __future__ import annotations

import asyncio

import pytest


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
    from app.core.llm import LLMClient

    client = LLMClient()
    client.gemini_client = object()

    loop = asyncio.get_running_loop()
    pending_worker = loop.create_future()

    def _never_finishing_executor(_executor, _func):
        return pending_worker

    monkeypatch.setattr(loop, "run_in_executor", _never_finishing_executor)

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

    loop = asyncio.get_running_loop()
    pending_worker = loop.create_future()

    class SpyEvent:
        last_instance: "SpyEvent | None" = None

        def __init__(self) -> None:
            self.was_set = False
            SpyEvent.last_instance = self

        def is_set(self) -> bool:
            return self.was_set

        def set(self) -> None:
            self.was_set = True

    def _never_finishing_executor(_executor, _func):
        return pending_worker

    monkeypatch.setattr(loop, "run_in_executor", _never_finishing_executor)
    monkeypatch.setattr(llm_module.threading, "Event", SpyEvent)

    async def _consume() -> None:
        async for _ in client._gemini_stream("prompt", "content"):
            pass

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert SpyEvent.last_instance is not None
    assert SpyEvent.last_instance.was_set is True
    await asyncio.sleep(0.25)
