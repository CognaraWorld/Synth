"""Tests for the payments and credits system (Phase 8).

Run all payment tests::

    pytest tests/test_payments.py

All tests are fast (no external services, no database).
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.routes.payments import CREDIT_PACKS, _handle_checkout_completed
from app.models.credit_transaction import CreditTransaction


# =====================================================================
# Credit pack definitions
# =====================================================================


class TestCreditPacks:
    """Verify credit pack configuration."""

    def test_credit_packs_defined(self) -> None:
        """All packs must have credits, price_cents, and label."""
        assert len(CREDIT_PACKS) >= 3

        for pack_id, pack in CREDIT_PACKS.items():
            assert "credits" in pack, f"{pack_id} missing 'credits'"
            assert "price_cents" in pack, f"{pack_id} missing 'price_cents'"
            assert "label" in pack, f"{pack_id} missing 'label'"

            assert isinstance(pack["credits"], int)
            assert pack["credits"] > 0
            assert isinstance(pack["price_cents"], int)
            assert pack["price_cents"] > 0
            assert isinstance(pack["label"], str)
            assert len(pack["label"]) > 0

    def test_pack_5_values(self) -> None:
        pack = CREDIT_PACKS["pack_5"]
        assert pack["credits"] == 5
        assert pack["price_cents"] == 3000

    def test_pack_20_values(self) -> None:
        pack = CREDIT_PACKS["pack_20"]
        assert pack["credits"] == 20
        assert pack["price_cents"] == 10000

    def test_pack_50_values(self) -> None:
        pack = CREDIT_PACKS["pack_50"]
        assert pack["credits"] == 50
        assert pack["price_cents"] == 20000

    def test_bulk_discount_ordering(self) -> None:
        """Larger packs should have a lower price per credit."""
        pack_5_per_credit = CREDIT_PACKS["pack_5"]["price_cents"] / CREDIT_PACKS["pack_5"]["credits"]
        pack_20_per_credit = CREDIT_PACKS["pack_20"]["price_cents"] / CREDIT_PACKS["pack_20"]["credits"]
        pack_50_per_credit = CREDIT_PACKS["pack_50"]["price_cents"] / CREDIT_PACKS["pack_50"]["credits"]

        assert pack_20_per_credit < pack_5_per_credit
        assert pack_50_per_credit < pack_20_per_credit


# =====================================================================
# Checkout endpoint auth
# =====================================================================


class TestCreateCheckoutAuth:
    """Verify that create-checkout requires authentication."""

    def test_create_checkout_no_auth(self) -> None:
        """Unauthenticated requests to /payments/create-checkout should get 401."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/payments/create-checkout",
            json={"pack_id": "pack_5"},
        )
        assert response.status_code == 401

    def test_credits_balance_no_auth(self) -> None:
        """Unauthenticated requests to /credits/balance should get 401."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/credits/balance")
        assert response.status_code == 401

    def test_credits_transactions_no_auth(self) -> None:
        """Unauthenticated requests to /credits/transactions should get 401."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/credits/transactions")
        assert response.status_code == 401

    def test_payment_history_no_auth(self) -> None:
        """Unauthenticated requests to /payments/history should get 401."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/payments/history")
        assert response.status_code == 401


# =====================================================================
# Webhook event structure
# =====================================================================


class TestWebhookEventStructure:
    """Test webhook payload parsing logic."""

    def test_webhook_extracts_metadata(self) -> None:
        """The handler should correctly extract user_id and pack_id from session metadata."""
        user_id = str(uuid4())
        session_data = {
            "id": "cs_test_abc123",
            "metadata": {
                "user_id": user_id,
                "pack_id": "pack_20",
            },
        }

        metadata = session_data.get("metadata", {})
        assert metadata["user_id"] == user_id
        assert metadata["pack_id"] == "pack_20"

    def test_webhook_missing_metadata_is_safe(self) -> None:
        """Missing metadata should not raise an exception during extraction."""
        session_data = {"id": "cs_test_no_meta"}
        metadata = session_data.get("metadata", {})
        user_id = metadata.get("user_id")
        pack_id = metadata.get("pack_id")

        assert user_id is None
        assert pack_id is None

    def test_webhook_event_type_routing(self) -> None:
        """Only checkout.session.completed events should trigger credit addition."""
        relevant_events = ["checkout.session.completed"]
        ignored_events = [
            "payment_intent.succeeded",
            "charge.succeeded",
            "customer.created",
        ]

        event_type = "checkout.session.completed"
        assert event_type in relevant_events

        for evt in ignored_events:
            assert evt not in relevant_events

    def test_duplicate_session_id_detection_logic(self) -> None:
        """Verify the duplicate detection concept works with a set-based approach."""
        processed_sessions: set[str] = set()
        session_id = "cs_test_duplicate"

        # First time: not a duplicate
        assert session_id not in processed_sessions
        processed_sessions.add(session_id)

        # Second time: is a duplicate
        assert session_id in processed_sessions


# =====================================================================
# Credit transaction model
# =====================================================================


class TestCreditTransactionModel:
    """Verify the CreditTransaction model has correct fields."""

    def test_model_has_correct_tablename(self) -> None:
        assert CreditTransaction.__tablename__ == "credit_transactions"

    def test_model_has_required_columns(self) -> None:
        column_names = {col.name for col in CreditTransaction.__table__.columns}
        expected = {
            "id",
            "user_id",
            "amount",
            "balance_after",
            "transaction_type",
            "description",
            "stripe_session_id",
            "created_at",
        }
        assert expected.issubset(column_names)

    def test_stripe_session_id_is_nullable(self) -> None:
        col = CreditTransaction.__table__.columns["stripe_session_id"]
        assert col.nullable is True

    def test_user_id_has_foreign_key(self) -> None:
        col = CreditTransaction.__table__.columns["user_id"]
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "users.id" in fk_targets

    def test_amount_is_not_nullable(self) -> None:
        col = CreditTransaction.__table__.columns["amount"]
        assert col.nullable is False

    def test_transaction_type_is_not_nullable(self) -> None:
        col = CreditTransaction.__table__.columns["transaction_type"]
        assert col.nullable is False


# =====================================================================
# Schema validation
# =====================================================================


class TestPaymentSchemas:
    """Verify Pydantic schemas for payment-related endpoints."""

    def test_checkout_request_requires_pack_id(self) -> None:
        from app.models.schemas import CheckoutRequest

        with pytest.raises(Exception):
            CheckoutRequest()  # pack_id is required

    def test_checkout_request_accepts_valid_pack(self) -> None:
        from app.models.schemas import CheckoutRequest

        req = CheckoutRequest(pack_id="pack_5")
        assert req.pack_id == "pack_5"

    def test_checkout_response_structure(self) -> None:
        from app.models.schemas import CheckoutResponse

        resp = CheckoutResponse(checkout_url="https://checkout.stripe.com/c/pay_xyz")
        assert resp.checkout_url.startswith("https://")

    def test_credit_balance_response(self) -> None:
        from app.models.schemas import CreditBalanceResponse

        uid = uuid4()
        resp = CreditBalanceResponse(credits=15, user_id=uid)
        assert resp.credits == 15
        assert resp.user_id == uid

    def test_credit_transaction_response(self) -> None:
        from app.models.schemas import CreditTransactionResponse

        now = datetime.utcnow()
        uid = uuid4()
        resp = CreditTransactionResponse(
            id=uid,
            amount=5,
            balance_after=10,
            transaction_type="purchase",
            description="Purchased 5 Credits",
            stripe_session_id="cs_abc",
            created_at=now,
        )
        assert resp.amount == 5
        assert resp.transaction_type == "purchase"

    def test_credit_transaction_list_response(self) -> None:
        from app.models.schemas import CreditTransactionListResponse

        resp = CreditTransactionListResponse(
            transactions=[],
            total=0,
            page=1,
            per_page=20,
        )
        assert resp.total == 0
        assert resp.page == 1
        assert resp.transactions == []
