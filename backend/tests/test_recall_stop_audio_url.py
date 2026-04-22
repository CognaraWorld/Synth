"""Regression test: stop_audio must DELETE /bot/{id}/output_audio/ — Recall's actual endpoint.

Previously the code POST'd to /bot/{id}/stop_output_audio which returns 404
in Recall.ai's API. The 404 handler treated it as "nothing playing" and
silently swallowed it — meaning clicking the Stop button in the live UI
never actually interrupted the bot's TTS playback.

The correct endpoint per
https://docs.recall.ai/reference/bot_output_audio_destroy
is HTTP DELETE on /bot/{id}/output_audio/ (with trailing slash).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stop_audio_uses_delete_output_audio_endpoint() -> None:
    """The stop URL must be DELETE /bot/{id}/output_audio/ — POST /stop_output_audio returns 404."""
    from app.meeting.recall_client import RecallClient

    client = RecallClient()

    captured: dict[str, str] = {}
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock(return_value=None)
    fake_response.status_code = 200

    async def fake_delete(url: str, **_kwargs):
        captured["method"] = "DELETE"
        captured["url"] = url
        return fake_response

    async def fake_post(url: str, **_kwargs):
        captured["method"] = "POST"
        captured["url"] = url
        return fake_response

    client._client.delete = fake_delete  # type: ignore[assignment]
    client._client.post = fake_post  # type: ignore[assignment]

    await client.stop_audio("test-bot-456")

    assert captured.get("method") == "DELETE", (
        f"stop_audio used HTTP {captured.get('method')} but Recall requires DELETE. "
        "POST /stop_output_audio returns 404 and the bot keeps speaking."
    )
    assert captured.get("url") == "/bot/test-bot-456/output_audio/", (
        f"Expected /bot/{{id}}/output_audio/ — got {captured.get('url')!r}. "
        "See https://docs.recall.ai/reference/bot_output_audio_destroy"
    )
