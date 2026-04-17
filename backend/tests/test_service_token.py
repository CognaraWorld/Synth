"""Tests for POST /api/auth/service-token endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.schemas import ServiceTokenRequest


def _mock_request(ip: str = "203.0.113.7") -> MagicMock:
    """Build a FastAPI ``Request`` stand-in that exposes only what auth.py reads."""
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock(host=ip)
    return request


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state():
    """Keep each test isolated — the IP-based limiter is shared process-wide."""
    from app.core.rate_limiter import reset_for_tests

    reset_for_tests()
    yield
    reset_for_tests()


class TestServiceTokenEndpoint:
    """Tests for the service-to-service token exchange endpoint."""

    @pytest.mark.asyncio
    async def test_rejects_missing_service_secret(self) -> None:
        from app.api.routes.auth import service_token

        db = AsyncMock()
        req = ServiceTokenRequest(
            email="user@example.com",
            name="Test User",
            service_secret="wrong-secret",
        )

        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.service_secret = "correct-secret"
            with pytest.raises(HTTPException) as exc_info:
                await service_token(req, _mock_request(), db)
            assert exc_info.value.status_code == 403
            assert "Invalid service secret" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_rejects_empty_service_secret_config(self) -> None:
        """Empty service_secret is treated as misconfiguration, not just a wrong guess."""
        from app.api.routes.auth import service_token

        db = AsyncMock()
        req = ServiceTokenRequest(
            email="user@example.com",
            name="Test User",
            service_secret="any-value",
        )

        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.service_secret = ""
            with pytest.raises(HTTPException) as exc_info:
                await service_token(req, _mock_request(), db)
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_rejects_default_shipped_service_secret(self) -> None:
        """The repo-shipped default is equivalent to being unconfigured."""
        from app.api.routes.auth import service_token

        db = AsyncMock()
        req = ServiceTokenRequest(
            email="user@example.com",
            name="Test User",
            service_secret="cognara-service-secret-dev",
        )

        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.service_secret = "cognara-service-secret-dev"
            with pytest.raises(HTTPException) as exc_info:
                await service_token(req, _mock_request(), db)
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_creates_new_user_on_first_exchange(self) -> None:
        from app.api.routes.auth import service_token

        db = AsyncMock()
        db.add = MagicMock()
        fake_result = MagicMock()
        fake_result.scalar_one_or_none.return_value = None  # user not found
        db.execute.return_value = fake_result

        req = ServiceTokenRequest(
            email="newuser@example.com",
            name="New User",
            service_secret="test-secret",
        )

        with (
            patch("app.api.routes.auth.settings") as mock_settings,
            patch("app.api.routes.auth.create_access_token", return_value="mock-jwt-token"),
        ):
            mock_settings.service_secret = "test-secret"

            result = await service_token(req, _mock_request(), db)

            # Verify user was added to DB
            db.add.assert_called()
            db.flush.assert_awaited()
            db.commit.assert_awaited()

            # Verify token returned
            assert result.access_token == "mock-jwt-token"
            assert result.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_returns_token_for_existing_user(self) -> None:
        from app.api.routes.auth import service_token

        fake_user = MagicMock()
        fake_user.id = uuid4()

        db = AsyncMock()
        fake_result = MagicMock()
        fake_result.scalar_one_or_none.return_value = fake_user
        db.execute.return_value = fake_result

        req = ServiceTokenRequest(
            email="existing@example.com",
            name="Existing User",
            service_secret="test-secret",
        )

        with (
            patch("app.api.routes.auth.settings") as mock_settings,
            patch("app.api.routes.auth.create_access_token", return_value="existing-jwt"),
        ):
            mock_settings.service_secret = "test-secret"

            result = await service_token(req, _mock_request(), db)

            # Should NOT create a new user
            db.flush.assert_not_awaited()
            db.commit.assert_not_awaited()

            assert result.access_token == "existing-jwt"

    @pytest.mark.asyncio
    async def test_grants_starter_credits_to_new_user(self) -> None:
        from app.api.routes.auth import service_token
        from app.models.database import DEFAULT_STARTER_CREDITS

        db = AsyncMock()
        db.add = MagicMock()
        fake_result = MagicMock()
        fake_result.scalar_one_or_none.return_value = None
        db.execute.return_value = fake_result

        req = ServiceTokenRequest(
            email="newuser@example.com",
            name="New User",
            service_secret="test-secret",
        )

        with (
            patch("app.api.routes.auth.settings") as mock_settings,
            patch("app.api.routes.auth.create_access_token", return_value="mock-jwt"),
        ):
            mock_settings.service_secret = "test-secret"

            await service_token(req, _mock_request(), db)

            # db.add is called twice: once for User, once for CreditTransaction
            assert db.add.call_count >= 2
            credit_call = db.add.call_args_list[1]
            credit_obj = credit_call[0][0]
            assert credit_obj.amount == DEFAULT_STARTER_CREDITS
            assert credit_obj.transaction_type == "free_credit"

    @pytest.mark.asyncio
    async def test_uses_timing_safe_comparison(self) -> None:
        """Verify that the endpoint uses hmac.compare_digest for secret comparison."""
        import inspect
        from app.api.routes.auth import service_token

        source = inspect.getsource(service_token)
        assert "hmac.compare_digest" in source, (
            "service_token must use hmac.compare_digest for timing-safe secret comparison"
        )

    @pytest.mark.asyncio
    async def test_rate_limits_after_five_attempts_per_ip(self) -> None:
        """6th call from the same IP within a minute must return 429."""
        from app.api.routes.auth import service_token

        db = AsyncMock()
        req = ServiceTokenRequest(
            email="user@example.com",
            name="Test User",
            service_secret="wrong",
        )
        request = _mock_request(ip="198.51.100.4")

        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.service_secret = "correct-secret"

            # 5 attempts are allowed (each rejected on secret mismatch, not rate limit)
            for _ in range(5):
                with pytest.raises(HTTPException) as exc_info:
                    await service_token(req, request, db)
                assert exc_info.value.status_code == 403

            # 6th attempt trips the rate limit
            with pytest.raises(HTTPException) as exc_info:
                await service_token(req, request, db)
            assert exc_info.value.status_code == 429

    def test_service_token_request_validates_email(self) -> None:
        with pytest.raises(Exception):
            ServiceTokenRequest(
                email="not-an-email",
                name="Test",
                service_secret="secret",
            )

    def test_service_token_request_validates_name_length(self) -> None:
        with pytest.raises(Exception):
            ServiceTokenRequest(
                email="user@example.com",
                name="",
                service_secret="secret",
            )

    def test_service_token_request_bounds_secret_length(self) -> None:
        """Oversized service_secret must be rejected before hitting hmac."""
        with pytest.raises(Exception):
            ServiceTokenRequest(
                email="user@example.com",
                name="Test",
                service_secret="x" * 1025,
            )
        # 1024 exactly should still be allowed
        ServiceTokenRequest(
            email="user@example.com",
            name="Test",
            service_secret="x" * 1024,
        )


class TestClientIP:
    """Validate _client_ip() rejects non-IP strings in forwarding headers."""

    def test_rejects_non_ip_xff_header(self) -> None:
        from app.api.routes.auth import _client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "; DROP TABLE users"}
        request.client = MagicMock(host="10.0.0.1")
        # Invalid XFF should fall through to the socket peer.
        assert _client_ip(request) == "10.0.0.1"

    def test_rejects_non_ip_real_ip_header(self) -> None:
        from app.api.routes.auth import _client_ip

        request = MagicMock()
        request.headers = {"x-real-ip": "not-an-ip"}
        request.client = MagicMock(host="10.0.0.2")
        assert _client_ip(request) == "10.0.0.2"

    def test_accepts_valid_ipv4(self) -> None:
        from app.api.routes.auth import _client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "203.0.113.42, 10.0.0.1"}
        request.client = MagicMock(host="127.0.0.1")
        assert _client_ip(request) == "203.0.113.42"

    def test_accepts_valid_ipv6(self) -> None:
        from app.api.routes.auth import _client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "2001:db8::1"}
        request.client = MagicMock(host="127.0.0.1")
        assert _client_ip(request) == "2001:db8::1"

    def test_returns_unknown_when_nothing_parseable(self) -> None:
        from app.api.routes.auth import _client_ip

        request = MagicMock()
        request.headers = {"x-forwarded-for": "bogus"}
        request.client = MagicMock(host="also-bogus")
        assert _client_ip(request) == "unknown"
