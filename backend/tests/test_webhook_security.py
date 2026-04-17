"""Security regression tests for the Recall webhook endpoint."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes import webhook


def _make_request(
    body: dict,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    request = MagicMock()
    request.headers = headers or {}
    request.body = AsyncMock(return_value=json.dumps(body).encode("utf-8"))
    return request


@pytest.mark.asyncio
async def test_recall_webhook_allows_unsigned_payload_when_secret_disabled() -> None:
    request = _make_request({"bot": {"id": "bot-1"}, "event": "transcript.data"})

    with (
        patch(
            "app.api.routes.webhook.get_settings",
            return_value=SimpleNamespace(webhook_secret=""),
        ),
        patch(
            "app.api.routes.webhook.asyncio.create_task",
            side_effect=lambda coro: (coro.close(), MagicMock())[1],
        ),
    ):
        response = await webhook.recall_webhook(request)

    assert response == {"status": "ok"}


def _make_workspace_headers(
    secret: str,
    body: bytes,
    *,
    timestamp: str = "1700000000",
    message_id: str = "msg_test_123",
) -> dict[str, str]:
    signing_key = webhook._urlsafe_b64decode_padded(secret.removeprefix("whsec_"))
    payload = f"{message_id}.{timestamp}.{body.decode('utf-8')}".encode("utf-8")
    signature = base64.urlsafe_b64encode(
        hmac.new(signing_key, payload, hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return {
        "webhook-id": message_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature}",
    }


@pytest.mark.asyncio
async def test_recall_webhook_accepts_valid_workspace_signature() -> None:
    secret = "whsec_" + base64.b64encode(b"recall-test-secret").decode("ascii")
    body = {"bot": {"id": "bot-1"}, "event": "transcript.data"}
    raw_body = json.dumps(body).encode("utf-8")
    request = _make_request(body, _make_workspace_headers(secret, raw_body))

    webhook._seen_nonces.clear()
    try:
        with (
            patch(
                "app.api.routes.webhook.get_settings",
                return_value=SimpleNamespace(webhook_secret=secret),
            ),
            patch("app.api.routes.webhook.time.time", return_value=1700000000.0),
            patch(
                "app.api.routes.webhook.asyncio.create_task",
                side_effect=lambda coro: (coro.close(), MagicMock())[1],
            ),
        ):
            response = await webhook.recall_webhook(request)
    finally:
        webhook._seen_nonces.clear()

    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_recall_webhook_accepts_urlsafe_workspace_signature() -> None:
    secret = "whsec_" + base64.urlsafe_b64encode(b"recall-test-secret\xff").decode("ascii").rstrip("=")
    body = {"bot": {"id": "bot-1"}, "event": "transcript.data"}
    raw_body = json.dumps(body).encode("utf-8")
    request = _make_request(body, _make_workspace_headers(secret, raw_body))

    webhook._seen_nonces.clear()
    try:
        with (
            patch(
                "app.api.routes.webhook.get_settings",
                return_value=SimpleNamespace(webhook_secret=secret),
            ),
            patch("app.api.routes.webhook.time.time", return_value=1700000000.0),
            patch(
                "app.api.routes.webhook.asyncio.create_task",
                side_effect=lambda coro: (coro.close(), MagicMock())[1],
            ),
        ):
            response = await webhook.recall_webhook(request)
    finally:
        webhook._seen_nonces.clear()

    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_recall_webhook_rejects_duplicate_replay_without_secret() -> None:
    request = _make_request(
        {"bot": {"id": "bot-1"}, "event": "transcript.data"},
        {"X-Recall-Timestamp": "1700000000"},
    )

    webhook._seen_nonces.clear()
    try:
        with (
            patch(
                "app.api.routes.webhook.get_settings",
                return_value=SimpleNamespace(webhook_secret=""),
            ),
            patch("app.api.routes.webhook.time.time", return_value=1700000000.0),
            patch(
                "app.api.routes.webhook.asyncio.create_task",
                side_effect=lambda coro: (coro.close(), MagicMock())[1],
            ),
        ):
            first_response = await webhook.recall_webhook(request)
            second_response = await webhook.recall_webhook(request)
    finally:
        webhook._seen_nonces.clear()

    assert first_response == {"status": "ok"}
    assert second_response.status_code == 409
    assert second_response.body == b'{"error":"duplicate"}'


def test_greeted_bot_tracking_is_pruned_when_terminal_events_are_missed() -> None:
    webhook._greeted_bots.clear()
    try:
        now = 10_000.0
        webhook._greeted_bots["bot-stale"] = now - webhook._GREETED_BOT_TTL_SECONDS - 1
        webhook._greeted_bots["bot-fresh"] = now

        webhook._prune_greeted_bots(now=now)

        assert "bot-stale" not in webhook._greeted_bots
        assert "bot-fresh" in webhook._greeted_bots
    finally:
        webhook._greeted_bots.clear()


def test_replay_nonce_depends_on_raw_body_and_timestamp() -> None:
    nonce_one = webhook._build_replay_nonce(
        b'{"bot":{"id":"bot-1"},"event":"transcript.data"}',
        "1700000000",
    )
    nonce_two = webhook._build_replay_nonce(
        b'{"bot":{"id":"bot-2"},"event":"transcript.data"}',
        "1700000000",
    )
    nonce_three = webhook._build_replay_nonce(
        b'{"bot":{"id":"bot-1"},"event":"transcript.data"}',
        "1700000001",
    )

    assert len(nonce_one) == 64
    assert nonce_one != nonce_two
    assert nonce_one != nonce_three
