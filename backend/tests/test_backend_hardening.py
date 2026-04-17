"""Focused tests for backend hardening regressions and audit trails."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.payments import CREDIT_PACKS
from app.context.documents import DocumentProcessor
from app.models.credit_transaction import CreditTransaction
from app.meeting.recall_client import RecallClientError
from app.models.schemas import MeetingCreate, UserCreate


class TestDocumentProcessorDependencyFallbacks:
    def test_parse_docx_reports_missing_dependency(self) -> None:
        processor = DocumentProcessor()

        def fake_import(module_name: str):
            if module_name == "docx":
                raise ModuleNotFoundError("No module named 'docx'")
            raise AssertionError(f"Unexpected import: {module_name}")

        with (
            patch("app.context.documents.os.path.isfile", return_value=True),
            patch("app.context.documents.importlib.import_module", side_effect=fake_import),
        ):
            with pytest.raises(RuntimeError, match="DOCX processing is unavailable"):
                processor.parse_docx("notes.docx")

    def test_parse_pdf_reports_missing_dependency(self) -> None:
        processor = DocumentProcessor()

        def fake_import(module_name: str):
            if module_name == "pdfplumber":
                raise ModuleNotFoundError("No module named 'pdfplumber'")
            raise AssertionError(f"Unexpected import: {module_name}")

        with (
            patch("app.context.documents.os.path.isfile", return_value=True),
            patch("app.context.documents.importlib.import_module", side_effect=fake_import),
        ):
            with pytest.raises(RuntimeError, match="PDF processing is unavailable"):
                processor.parse_pdf("notes.pdf")


class TestAuthRegistrationHardening:
    @staticmethod
    def _request() -> MagicMock:
        return MagicMock(headers={}, client=MagicMock(host="127.0.0.1"))

    @pytest.mark.asyncio
    async def test_register_requires_password_for_email_provider(self) -> None:
        from app.api.routes.auth import register

        db = AsyncMock()

        with (
            patch("app.api.routes.auth.check_named_limit", new=AsyncMock()),
            pytest.raises(HTTPException, match="Password is required"),
        ):
            await register(
                UserCreate(
                    email="user@example.com",
                    name="Test User",
                    password=None,
                    provider="email",
                ),
                request=self._request(),
                db=db,
            )

    @pytest.mark.asyncio
    async def test_register_rejects_short_password(self) -> None:
        from app.api.routes.auth import register

        db = AsyncMock()

        with (
            patch("app.api.routes.auth.check_named_limit", new=AsyncMock()),
            pytest.raises(HTTPException, match="at least 8 characters"),
        ):
            await register(
                UserCreate(
                    email="user@example.com",
                    name="Test User",
                    password="short",
                    provider="email",
                ),
                request=self._request(),
                db=db,
            )

    @pytest.mark.asyncio
    async def test_register_creates_starter_credit_transaction(self) -> None:
        from app.api.routes.auth import register
        from app.models.database import DEFAULT_STARTER_CREDITS

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.return_value = query_result
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        async def flush_side_effect() -> None:
            user = db.add.call_args_list[0].args[0]
            user.id = uuid4()
            user.credits = DEFAULT_STARTER_CREDITS
            user.created_at = datetime.now(timezone.utc)

        db.flush.side_effect = flush_side_effect

        with (
            patch("app.api.routes.auth.check_named_limit", new=AsyncMock()),
            patch("app.api.routes.auth.pwd_context.hash", return_value="hashed-password"),
        ):
            result = await register(
                UserCreate(
                    email="user@example.com",
                    name="Test User",
                    password="StrongPass123",
                    provider="email",
                ),
                request=self._request(),
                db=db,
            )

        added_objects = [call.args[0] for call in db.add.call_args_list]
        transaction = next(obj for obj in added_objects if isinstance(obj, CreditTransaction))
        assert transaction.transaction_type == "free_credit"
        assert transaction.amount == DEFAULT_STARTER_CREDITS
        assert transaction.balance_after == DEFAULT_STARTER_CREDITS
        assert result.credits == DEFAULT_STARTER_CREDITS


class TestStartupMigrations:
    def test_run_migrations_backfills_registration_columns_for_legacy_schema(self) -> None:
        from app.main import _run_migrations

        inspector = MagicMock()
        inspector.has_table.side_effect = (
            lambda table_name: table_name in {"documents", "users", "credit_transactions"}
        )

        def get_columns(table_name: str) -> list[dict[str, object]]:
            if table_name == "documents":
                return [{"name": "id"}]
            if table_name == "users":
                return [{"name": "id"}, {"name": "email"}, {"name": "hashed_password"}]
            if table_name == "credit_transactions":
                # Simulate legacy schema missing balance_after and stripe_session_id
                return [
                    {"name": "id", "nullable": False},
                    {"name": "user_id", "nullable": False},
                    {"name": "meeting_id", "nullable": False},
                    {"name": "amount", "nullable": True},
                    {"name": "transaction_type", "nullable": True},
                    {"name": "description", "nullable": True},
                    {"name": "created_at", "nullable": True},
                ]
            raise AssertionError(f"Unexpected table lookup: {table_name}")

        inspector.get_columns.side_effect = get_columns

        connection = MagicMock()
        connection.dialect.name = "postgresql"

        with patch("app.main.inspect", return_value=inspector):
            _run_migrations(connection)

        executed_sql = [str(call.args[0]).strip() for call in connection.execute.call_args_list]
        assert "ALTER TABLE users ADD COLUMN IF NOT EXISTS provider VARCHAR(50)" in executed_sql
        assert "ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER" in executed_sql
        assert "UPDATE users SET provider = 'email' WHERE provider IS NULL" in executed_sql
        assert "UPDATE users SET credits = 60 WHERE credits IS NULL" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN provider SET DEFAULT 'email'" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN credits SET DEFAULT 60" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN provider SET NOT NULL" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN credits SET NOT NULL" in executed_sql
        assert "ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS balance_after INTEGER" in executed_sql
        assert (
            "ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS stripe_session_id VARCHAR(255)"
            in executed_sql
        )
        assert (
            "ALTER TABLE credit_transactions ALTER COLUMN meeting_id DROP NOT NULL" in executed_sql
        )
        assert (
            "UPDATE credit_transactions SET amount = 0 WHERE amount IS NULL"
            in executed_sql
        )
        assert (
            "UPDATE credit_transactions "
            "SET transaction_type = 'legacy' "
            "WHERE transaction_type IS NULL OR transaction_type = ''"
            in executed_sql
        )
        assert (
            "UPDATE credit_transactions "
            "SET description = 'Legacy credit transaction' "
            "WHERE description IS NULL OR description = ''"
            in executed_sql
        )
        assert (
            "UPDATE credit_transactions "
            "SET balance_after = COALESCE(balance_after, amount, 0) "
            "WHERE balance_after IS NULL"
            in executed_sql
        )
        assert (
            "ALTER TABLE credit_transactions ALTER COLUMN balance_after SET NOT NULL" in executed_sql
        )
        assert "ALTER TABLE credit_transactions ALTER COLUMN amount SET NOT NULL" in executed_sql
        assert (
            "ALTER TABLE credit_transactions ALTER COLUMN transaction_type SET NOT NULL"
            in executed_sql
        )
        assert (
            "ALTER TABLE credit_transactions ALTER COLUMN description SET NOT NULL"
            in executed_sql
        )
        assert "ALTER TABLE credit_transactions ALTER COLUMN amount SET DEFAULT 0" in executed_sql
        assert (
            "ALTER TABLE credit_transactions ALTER COLUMN balance_after SET DEFAULT 0"
            in executed_sql
        )
        assert (
            "ALTER TABLE credit_transactions ALTER COLUMN transaction_type SET DEFAULT 'legacy'"
            in executed_sql
        )
        assert (
            "ALTER TABLE credit_transactions "
            "ALTER COLUMN description SET DEFAULT 'Legacy credit transaction'"
            in executed_sql
        )


class TestMeetingCreditAuditTrail:
    @pytest.mark.asyncio
    async def test_create_meeting_reserves_5_minutes(self) -> None:
        """create_meeting atomically reserves 5 minutes from user balance."""
        from app.api.routes.meetings import create_meeting

        user_id = uuid4()
        agent_id = uuid4()
        current_user = MagicMock(id=user_id, credits=60)
        agent = MagicMock(id=agent_id, user_id=user_id)

        # First call: active meetings count check (< 20)
        active_count_result = MagicMock()
        active_count_result.scalar.return_value = 0
        # Second call: atomic reserve (rowcount=1 means success)
        reserve_result = MagicMock(rowcount=1)
        # Third call: agent lookup
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = agent

        db = AsyncMock()
        db.execute.side_effect = [active_count_result, reserve_result, agent_result]
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_settings = MagicMock(recall_api_key="", deepgram_api_key="")
        with (
            patch("app.api.routes.meetings.detect_platform", return_value="zoom"),
            patch("app.api.routes.meetings.get_settings", return_value=mock_settings),
        ):
            meeting = await create_meeting(
                MeetingCreate(
                    agent_id=agent_id,
                    meeting_link="https://zoom.us/j/123456789",
                ),
                current_user=current_user,
                db=db,
            )

        # Meeting created with credits_used=0 (billing happens at stop)
        created_meeting = db.add.call_args.args[0]
        assert created_meeting.credits_used == 0
        assert created_meeting.status == "pending"
        assert created_meeting.agent_id == agent_id

    @pytest.mark.asyncio
    async def test_refund_meeting_credit_blocks_legacy_duplicate_refund(self) -> None:
        from app.api.routes.credits import refund_meeting_credit

        meeting_id = uuid4()
        current_user = MagicMock(id=uuid4(), credits=2)
        meeting = MagicMock(id=meeting_id, user_id=current_user.id, status="failed", credits_used=1)
        legacy_refund = MagicMock()

        meeting_result = MagicMock()
        meeting_result.scalar_one_or_none.return_value = meeting
        refund_result = MagicMock()
        refund_result.scalar_one_or_none.return_value = legacy_refund

        db = AsyncMock()
        db.execute.side_effect = [meeting_result, refund_result]

        with pytest.raises(HTTPException, match="already been refunded"):
            await refund_meeting_credit(
                meeting_id=meeting_id,
                current_user=current_user,
                db=db,
            )

    @pytest.mark.asyncio
    async def test_refund_meeting_credit_records_refund_transaction(self) -> None:
        from app.api.routes.credits import refund_meeting_credit

        meeting_id = uuid4()
        current_user = MagicMock(id=uuid4(), credits=2)
        meeting = MagicMock(id=meeting_id, user_id=current_user.id, status="failed", credits_used=2)

        # 1st call: meeting lookup
        meeting_result = MagicMock()
        meeting_result.scalar_one_or_none.return_value = meeting
        # 2nd call: existing refund check
        refund_result = MagicMock()
        refund_result.scalar_one_or_none.return_value = None
        # 3rd call: atomic credit update with .returning() -> new balance
        update_result = MagicMock()
        update_result.scalar_one.return_value = 4  # new balance after refund

        db = AsyncMock()
        db.execute.side_effect = [meeting_result, refund_result, update_result]
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        transaction = await refund_meeting_credit(
            meeting_id=meeting_id,
            current_user=current_user,
            db=db,
        )

        created_transaction = db.add.call_args.args[0]
        assert created_transaction.meeting_id == meeting_id
        assert created_transaction.amount == 2
        assert created_transaction.balance_after == 4
        assert created_transaction.transaction_type == "refund"

    @pytest.mark.asyncio
    async def test_create_meeting_refunds_reserved_credits_on_recall_failure(self) -> None:
        from app.api.routes.meetings import create_meeting

        user_id = uuid4()
        agent_id = uuid4()
        current_user = MagicMock(id=user_id, credits=60)
        agent = MagicMock(
            id=agent_id,
            user_id=user_id,
            name="Synth",
            mode="general",
            persona_id="general",
            description="",
            system_prompt="",
            voice="female",
        )

        active_count_result = MagicMock()
        active_count_result.scalar.return_value = 0
        reserve_result = MagicMock(rowcount=1)
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = agent
        refund_result = MagicMock()

        db = AsyncMock()
        db.execute.side_effect = [active_count_result, reserve_result, agent_result, refund_result]
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_recall = MagicMock()
        mock_recall.create_bot = AsyncMock(side_effect=RecallClientError("boom"))
        mock_recall.close = AsyncMock()

        settings = MagicMock(
            recall_api_key="recall-key",
            gemini_api_key="gemini-key",
            webhook_base_url="https://example.com",
        )

        with (
            patch("app.api.routes.meetings.detect_platform", return_value="zoom"),
            patch("app.api.routes.meetings.get_settings", return_value=settings),
            patch("app.api.routes.meetings.RecallClient", return_value=mock_recall),
        ):
            with pytest.raises(HTTPException, match="Failed to deploy meeting bot"):
                await create_meeting(
                    MeetingCreate(
                        agent_id=agent_id,
                        meeting_link="https://zoom.us/j/123456789",
                    ),
                    current_user=current_user,
                    db=db,
                )

        created_meeting = db.add.call_args.args[0]
        assert created_meeting.status == "failed"
        assert db.execute.await_count == 4
        db.commit.assert_awaited_once()
        mock_recall.close.assert_awaited_once()


class TestWebhookUuidHardening:
    @pytest.mark.asyncio
    async def test_checkout_completed_ignores_invalid_user_id(self) -> None:
        from app.api.routes.payments import _handle_checkout_completed

        db = AsyncMock()

        await _handle_checkout_completed(
            {
                "id": "cs_test_invalid_user",
                "metadata": {
                    "user_id": "not-a-uuid",
                    "pack_id": "pack_5",
                },
            },
            db,
        )

        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_checkout_completed_processes_valid_user_id(self) -> None:
        from app.api.routes.payments import _handle_checkout_completed

        user_id = uuid4()
        user = MagicMock(id=user_id, credits=1)

        user_lookup = MagicMock()
        user_lookup.scalar_one_or_none.return_value = user
        duplicate_check = MagicMock()
        duplicate_check.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.side_effect = [user_lookup, duplicate_check]
        db.add = MagicMock()
        db.commit = AsyncMock()

        await _handle_checkout_completed(
            {
                "id": "cs_test_valid_user",
                "metadata": {
                    "user_id": str(user_id),
                    "pack_id": "pack_5",
                },
            },
            db,
        )

        transaction = db.add.call_args.args[0]
        assert user.credits == 6
        assert transaction.user_id == user_id
        assert transaction.amount == CREDIT_PACKS["pack_5"]["credits"]
        db.commit.assert_awaited_once()
