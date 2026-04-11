"""Regression tests for LLM streaming cancellation behavior."""

from __future__ import annotations

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
