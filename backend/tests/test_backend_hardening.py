"""Focused tests for backend hardening regressions and audit trails."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.payments import CREDIT_PACKS
from app.context.documents import DocumentProcessor
from app.models.credit_transaction import CreditTransaction
from app.models.schemas import MeetingCreate, UserCreate


class TestDocumentProcessorDependencyFallbacks:
    def test_parse_docx_reports_missing_dependency(self, tmp_path: Path) -> None:
        file_path = tmp_path / "notes.docx"
        file_path.write_text("placeholder", encoding="utf-8")
        processor = DocumentProcessor()

        def fake_import(module_name: str):
            if module_name == "docx":
                raise ModuleNotFoundError("No module named 'docx'")
            raise AssertionError(f"Unexpected import: {module_name}")

        with patch("app.context.documents.importlib.import_module", side_effect=fake_import):
            with pytest.raises(RuntimeError, match="DOCX processing is unavailable"):
                processor.parse_docx(str(file_path))

    def test_parse_pdf_reports_missing_dependency(self, tmp_path: Path) -> None:
        file_path = tmp_path / "notes.pdf"
        file_path.write_text("placeholder", encoding="utf-8")
        processor = DocumentProcessor()

        def fake_import(module_name: str):
            if module_name == "pdfplumber":
                raise ModuleNotFoundError("No module named 'pdfplumber'")
            raise AssertionError(f"Unexpected import: {module_name}")

        with patch("app.context.documents.importlib.import_module", side_effect=fake_import):
            with pytest.raises(RuntimeError, match="PDF processing is unavailable"):
                processor.parse_pdf(str(file_path))


class TestAuthRegistrationHardening:
    @pytest.mark.asyncio
    async def test_register_requires_password_for_email_provider(self) -> None:
        from app.api.routes.auth import register

        db = AsyncMock()

        with pytest.raises(HTTPException, match="Password is required"):
            await register(
                UserCreate(
                    email="user@example.com",
                    name="Test User",
                    password=None,
                    provider="email",
                ),
                db=db,
            )

    @pytest.mark.asyncio
    async def test_register_rejects_short_password(self) -> None:
        from app.api.routes.auth import register

        db = AsyncMock()

        with pytest.raises(HTTPException, match="at least 8 characters"):
            await register(
                UserCreate(
                    email="user@example.com",
                    name="Test User",
                    password="short",
                    provider="email",
                ),
                db=db,
            )

    @pytest.mark.asyncio
    async def test_register_creates_starter_credit_transaction(self) -> None:
        from app.api.routes.auth import register

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
            user.credits = 3
            user.created_at = datetime.now(timezone.utc)

        db.flush.side_effect = flush_side_effect

        with patch("app.api.routes.auth.pwd_context.hash", return_value="hashed-password"):
            result = await register(
                UserCreate(
                    email="user@example.com",
                    name="Test User",
                    password="strong-pass-123",
                    provider="email",
                ),
                db=db,
            )

        added_objects = [call.args[0] for call in db.add.call_args_list]
        transaction = next(obj for obj in added_objects if isinstance(obj, CreditTransaction))
        assert transaction.transaction_type == "free_credit"
        assert transaction.amount == 3
        assert transaction.balance_after == 3
        assert result.credits == 3


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
                return [
                    {"name": "id", "nullable": False},
                    {"name": "user_id", "nullable": False},
                    {"name": "meeting_id", "nullable": False},
                    {"name": "amount", "nullable": False},
                    {"name": "transaction_type", "nullable": False},
                    {"name": "description", "nullable": False},
                    {"name": "created_at", "nullable": True},
                ]
            raise AssertionError(f"Unexpected table lookup: {table_name}")

        inspector.get_columns.side_effect = get_columns

        connection = MagicMock()
        connection.dialect.name = "postgresql"

        with patch("app.main.inspect", return_value=inspector):
            _run_migrations(connection)

        executed_sql = [str(call.args[0]).strip() for call in connection.execute.call_args_list]
        assert "ALTER TABLE users ADD COLUMN provider VARCHAR(50)" in executed_sql
        assert "ALTER TABLE users ADD COLUMN credits INTEGER" in executed_sql
        assert "UPDATE users SET provider = 'email' WHERE provider IS NULL" in executed_sql
        assert "UPDATE users SET credits = 3 WHERE credits IS NULL" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN provider SET DEFAULT 'email'" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN credits SET DEFAULT 3" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN provider SET NOT NULL" in executed_sql
        assert "ALTER TABLE users ALTER COLUMN credits SET NOT NULL" in executed_sql
        assert "ALTER TABLE credit_transactions ADD COLUMN balance_after INTEGER" in executed_sql
        assert (
            "ALTER TABLE credit_transactions ADD COLUMN stripe_session_id VARCHAR(255)"
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
    async def test_create_meeting_records_credit_transaction(self) -> None:
        from app.api.routes.meetings import create_meeting

        user_id = uuid4()
        agent_id = uuid4()
        current_user = MagicMock(id=user_id, credits=3)
        agent = MagicMock(id=agent_id, user_id=user_id)

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = agent

        db = AsyncMock()
        db.execute.return_value = query_result
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        async def flush_side_effect() -> None:
            for call in db.add.call_args_list:
                obj = call.args[0]
                if hasattr(obj, "meeting_link"):
                    obj.id = uuid4()
                    break

        db.flush.side_effect = flush_side_effect

        with patch("app.api.routes.meetings.detect_platform", return_value="zoom"):
            meeting = await create_meeting(
                MeetingCreate(
                    agent_id=agent_id,
                    meeting_link="https://zoom.us/j/123456789",
                ),
                current_user=current_user,
                db=db,
            )

        added_objects = [call.args[0] for call in db.add.call_args_list]
        transaction = next(obj for obj in added_objects if isinstance(obj, CreditTransaction))

        assert current_user.credits == 2
        assert transaction.transaction_type == "meeting_used"
        assert transaction.amount == -1
        assert transaction.balance_after == 2
        assert transaction.meeting_id == meeting.id

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

        meeting_result = MagicMock()
        meeting_result.scalar_one_or_none.return_value = meeting
        refund_result = MagicMock()
        refund_result.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.side_effect = [meeting_result, refund_result]
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        transaction = await refund_meeting_credit(
            meeting_id=meeting_id,
            current_user=current_user,
            db=db,
        )

        created_transaction = db.add.call_args.args[0]
        assert current_user.credits == 4
        assert created_transaction.meeting_id == meeting_id
        assert created_transaction.amount == 2
        assert created_transaction.balance_after == 4
        assert created_transaction.transaction_type == "refund"
        assert transaction is created_transaction


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

        duplicate_check = MagicMock()
        duplicate_check.scalar_one_or_none.return_value = None
        user_lookup = MagicMock()
        user_lookup.scalar_one_or_none.return_value = user

        db = AsyncMock()
        db.execute.side_effect = [duplicate_check, user_lookup]
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
