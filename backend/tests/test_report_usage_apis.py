"""Tests for backend report library and usage record APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestReportFinalization:
    @pytest.mark.asyncio
    async def test_finalize_meeting_artifacts_persists_report_and_usage(
        self, tmp_path: Path
    ) -> None:
        from app.meeting.reporting import finalize_meeting_artifacts

        meeting = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
            meeting_link="https://zoom.us/j/123456789",
            platform="zoom",
            transcript="Alice: Let's ship the report feature today.",
            started_at=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 3, 10, 42, tzinfo=timezone.utc),
            duration_minutes=42.0,
            summary=None,
        )
        current_user = SimpleNamespace(email="owner@example.com")

        summary_payload = {
            "content": "The team aligned on shipping the report feature.",
            "key_points": ["Backend slice stays independent of calendar sync."],
            "action_items": ["Ship report endpoints today."],
            "decisions": ["Keep usage minute-based in dashboard APIs."],
        }

        generator = MagicMock()
        generator.generate = AsyncMock(return_value=summary_payload)
        generator.export_pdf.return_value = b"%PDF-1.4 synthetic"
        generator.export_docx.return_value = b"PK synthetic docx"

        sender = MagicMock()
        sender.is_configured.return_value = False
        sender.send_summary_email = AsyncMock(return_value=False)

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        db.execute.return_value = execute_result

        async def refresh_side_effect(model) -> None:
            if not getattr(model, "id", None):
                model.id = uuid4()
            if not getattr(model, "created_at", None):
                model.created_at = datetime.now(timezone.utc)
            if hasattr(model, "updated_at") and not getattr(model, "updated_at", None):
                model.updated_at = model.created_at

        db.refresh.side_effect = refresh_side_effect

        settings = SimpleNamespace(summary_dir=str(tmp_path))

        report, usage_record = await finalize_meeting_artifacts(
            db=db,
            meeting=meeting,
            current_user=current_user,
            settings=settings,
            generator=generator,
            sender=sender,
        )

        added_models = [call.args[0] for call in db.add.call_args_list]
        assert len(added_models) == 2
        assert report in added_models
        assert usage_record in added_models
        assert report.email_delivery_status == "skipped"
        assert Path(report.pdf_path).exists()
        assert Path(report.docx_path).exists()
        assert usage_record.minutes_used == 42.0
        assert usage_record.meeting_id == meeting.id


class TestReportsApi:
    def test_meeting_summary_response_hides_server_paths(self) -> None:
        from app.models.schemas import MeetingSummaryResponse

        report_id = uuid4()
        summary = SimpleNamespace(
            id=report_id,
            content="Long-form summary",
            key_points='["Budget approved"]',
            action_items='["Send notes"]',
            decisions='["Proceed with rollout"]',
            pdf_path="C:/reports/a.pdf",
            docx_path=None,
            email_delivery_status="sent",
            email_delivered_at=datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 4, 3, 10, 50, tzinfo=timezone.utc),
        )

        response = MeetingSummaryResponse.model_validate(summary)

        assert response.has_pdf is True
        assert response.has_docx is False
        assert response.pdf_download_path == f"/api/reports/{report_id}/download/pdf"
        assert "pdf_path" not in response.model_dump()
        assert "docx_path" not in response.model_dump()

    @pytest.mark.asyncio
    async def test_list_reports_returns_dashboard_friendly_payload(self) -> None:
        from app.api.routes.reports import list_reports

        current_user = SimpleNamespace(id=uuid4())
        meeting = SimpleNamespace(
            id=uuid4(),
            user_id=current_user.id,
            platform="zoom",
            meeting_link="https://zoom.us/j/123456789",
            started_at=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 3, 10, 42, tzinfo=timezone.utc),
            duration_minutes=42.0,
        )
        report = SimpleNamespace(
            id=uuid4(),
            meeting_id=meeting.id,
            meeting=meeting,
            content="Long-form summary",
            key_points='["Budget approved"]',
            action_items='["Send notes"]',
            decisions='["Proceed with rollout"]',
            pdf_path="C:/reports/a.pdf",
            docx_path=None,
            email_delivery_status="sent",
            email_delivered_at=datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 4, 3, 10, 50, tzinfo=timezone.utc),
        )

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [report]

        db = AsyncMock()
        db.execute.side_effect = [count_result, data_result]

        response = await list_reports(
            page=1,
            per_page=20,
            current_user=current_user,
            db=db,
        )

        assert response.total == 1
        assert response.reports[0].meeting_id == meeting.id
        assert response.reports[0].action_items == ["Send notes"]
        assert response.reports[0].has_pdf is True
        assert response.reports[0].has_docx is False


class TestUsageApi:
    @pytest.mark.asyncio
    async def test_stop_meeting_ends_active_meeting(self) -> None:
        from app.api.routes.meetings import stop_meeting

        current_user = SimpleNamespace(id=uuid4(), email="owner@example.com")
        meeting = SimpleNamespace(
            id=uuid4(),
            user_id=current_user.id,
            status="active",
            bot_id=None,
            started_at=datetime(2026, 4, 3, 10, 0),  # naive UTC to match code
            ended_at=None,
            duration_minutes=None,
            credits_used=0,
        )
        # 1st execute: meeting lookup
        lookup_result = MagicMock()
        lookup_result.scalar_one_or_none.return_value = meeting
        # 2nd execute: idempotent billing update (rowcount=1 means we won the race)
        bill_result = MagicMock(rowcount=1)
        # 3rd execute: settle credits
        settle_result = MagicMock()

        db = AsyncMock()
        db.execute.side_effect = [lookup_result, bill_result, settle_result]
        db.commit = AsyncMock()

        async def refresh_side_effect(obj):
            # Simulate DB refresh after SQL-level update
            obj.status = "ended"

        db.refresh = AsyncMock(side_effect=refresh_side_effect)

        with patch("app.api.routes.meetings.get_bot_engine") as mock_engine:
            mock_engine.return_value._sessions_by_bot_id = {}
            response = await stop_meeting(
                meeting_id=meeting.id,
                current_user=current_user,
                db=db,
            )

        assert response.status == "ended"

    @pytest.mark.asyncio
    async def test_get_usage_summary_returns_month_totals(self) -> None:
        from app.api.routes.usage import get_usage_summary

        current_user = SimpleNamespace(id=uuid4())

        aggregate_result = MagicMock()
        aggregate_result.one.return_value = (2, 87.5)

        db = AsyncMock()
        db.execute.return_value = aggregate_result

        response = await get_usage_summary(
            year=2026,
            month=4,
            current_user=current_user,
            db=db,
        )

        assert response.meeting_count == 2
        assert response.total_minutes == 87.5
        assert response.average_minutes == 43.75


class TestReportExportSecurity:
    def test_resolve_export_path_rejects_paths_outside_summary_dir(self, tmp_path: Path) -> None:
        from app.meeting.reporting import resolve_report_export_path

        with pytest.raises(ValueError, match="outside the configured summary directory"):
            resolve_report_export_path(
                raw_path=str(tmp_path.parent / "escape.pdf"),
                summary_dir=str(tmp_path),
            )
