"""Regression test: stop_bot must POST to /bot/{id}/leave_call/ — Recall's actual endpoint.

Previously the code POST'd to /bot/{id}/leave which returns 404 (URL doesn't exist
in Recall's API). The 404 handler treated it as "bot already gone" and silently
marked the session ended — but the bot remained in the meeting and kept streaming
transcripts. From the user's perspective, clicking "Leave meeting" did nothing.

The correct endpoint is documented at
https://docs.recall.ai/reference/bot_leave_call_create
and is /bot/{id}/leave_call/ (with the _call suffix and trailing slash).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stop_bot_uses_leave_call_endpoint() -> None:
    """The leave URL must be /bot/{id}/leave_call/ — using just /leave returns 404."""
    from app.meeting.recall_client import RecallClient

    client = RecallClient()

    # Mock the underlying httpx client and the retry wrapper so we can
    # intercept the URL without making a real network call.
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock(return_value=None)
    fake_response.status_code = 200

    captured: dict[str, str] = {}

    async def fake_run_with_retry(_label: str, fn):
        # Invoke the lambda so we can record which URL it would have hit.
        # The lambda calls self._client.post(url) and returns a coroutine.
        coroutine = fn()
        return await coroutine

    async def fake_post(url: str, **_kwargs):
        captured["url"] = url
        return fake_response

    client._client.post = fake_post  # type: ignore[assignment]

    with patch.object(client, "_run_with_retry", new=fake_run_with_retry):
        await client.stop_bot("test-bot-123")

    assert captured["url"] == "/bot/test-bot-123/leave_call/", (
        f"Expected /bot/{{id}}/leave_call/ — got {captured['url']!r}. "
        "The /leave URL returns 404 in Recall.ai's API and the bot will "
        "remain in the meeting. See "
        "https://docs.recall.ai/reference/bot_leave_call_create"
    )


@pytest.mark.asyncio
async def test_stop_bot_treats_404_as_already_gone() -> None:
    """A 404 should still be treated as 'already gone' for the rare case where
    the bot truly was deleted (e.g. user manually killed it). This must not
    raise — we keep the backend's ability to clean up state on real 404s."""
    import httpx

    from app.meeting.recall_client import RecallClient

    client = RecallClient()

    fake_response = MagicMock()
    fake_response.status_code = 404
    fake_response.text = "not found"

    error = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=fake_response
    )

    async def raise_404(_label: str, _fn):
        raise error

    with patch.object(client, "_run_with_retry", new=raise_404):
        # Must not raise — 404 is expected for already-departed bots
        await client.stop_bot("ghost-bot")
