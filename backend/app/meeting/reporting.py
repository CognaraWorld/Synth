"""Persistence helpers for generated meeting reports and usage records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.meeting.email_sender import EmailSender
from app.meeting.summary import SummaryGenerator
from app.models.database import AsyncSessionLocal, Meeting, MeetingSummary, UsageRecord
from app.utils.report_data import serialize_summary_items

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _export_report_artifacts(
    generator: SummaryGenerator,
    summary_payload: dict[str, Any],
    meeting_info: dict[str, str],
    summary_dir: Path,
    meeting_id,
) -> tuple[Path, Path, bytes, bytes]:
    """Generate and write report exports in a worker thread."""
    summary_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = summary_dir / f"{meeting_id}.pdf"
    docx_path = summary_dir / f"{meeting_id}.docx"

    pdf_bytes = generator.export_pdf(summary_payload, meeting_info=meeting_info)
    docx_bytes = generator.export_docx(summary_payload, meeting_info=meeting_info)
    pdf_path.write_bytes(pdf_bytes)
    docx_path.write_bytes(docx_bytes)
    return pdf_path, docx_path, pdf_bytes, docx_bytes


def calculate_minutes_used(meeting: Meeting) -> float:
    """Compute the duration to record for dashboard usage."""
    if meeting.duration_minutes is not None:
        return round(max(float(meeting.duration_minutes), 0.0), 2)

    if meeting.started_at and meeting.ended_at:
        duration = (meeting.ended_at - meeting.started_at).total_seconds() / 60
        return round(max(duration, 0.0), 2)

    return 0.0


def resolve_report_export_path(raw_path: str, summary_dir: str) -> Path:
    """Resolve a stored report path and ensure it stays under the summary directory."""
    base_dir = Path(summary_dir).resolve()
    candidate = Path(raw_path).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(
            "Report export path is outside the configured summary directory"
        ) from exc
    return candidate


def build_meeting_info(meeting: Meeting) -> dict[str, str]:
    """Build the metadata block used by exporters and email delivery."""
    reference_time = meeting.ended_at or meeting.started_at or meeting.created_at or _utcnow()
    minutes_used = calculate_minutes_used(meeting)
    duration_label = f"{minutes_used:.2f} min" if minutes_used else "0.00 min"
    return {
        "date": reference_time.strftime("%Y-%m-%d"),
        "duration": duration_label,
        "platform": str(meeting.platform),
    }


async def upsert_usage_record(
    db: AsyncSession,
    meeting: Meeting,
) -> UsageRecord:
    """Create or update the per-meeting usage record used by dashboard billing views."""
    result = await db.execute(select(UsageRecord).where(UsageRecord.meeting_id == meeting.id))
    usage_record = result.scalar_one_or_none()

    if usage_record is None:
        usage_record = UsageRecord(
            user_id=meeting.user_id,
            meeting_id=meeting.id,
        )
        db.add(usage_record)
        meeting.usage_record = usage_record

    usage_record.minutes_used = calculate_minutes_used(meeting)
    usage_record.recorded_at = (
        meeting.ended_at or meeting.started_at or meeting.created_at or _utcnow()
    )
    return usage_record


async def finalize_meeting_artifacts(
    db: AsyncSession,
    meeting: Meeting,
    current_user: Any,
    settings: Any,
    generator: SummaryGenerator | None = None,
    sender: EmailSender | None = None,
) -> tuple[MeetingSummary, UsageRecord]:
    """Generate report artifacts and sync the meeting's usage record."""
    generator = generator or SummaryGenerator()
    sender = sender or EmailSender()

    existing = meeting.summary
    if existing is not None and existing.email_delivery_status == "sent":
        pdf_ok = bool(existing.pdf_path) and Path(existing.pdf_path).is_file()
        docx_ok = bool(existing.docx_path) and Path(existing.docx_path).is_file()
        if pdf_ok and docx_ok:
            logger.info(
                "Meeting %s report already finalized and emailed; skipping duplicate run",
                meeting.id,
            )
            usage_record = await upsert_usage_record(db=db, meeting=meeting)
            await db.flush()
            return existing, usage_record

    meeting_info = build_meeting_info(meeting)

    # Use the best available transcript source: DB field first, then
    # check if the meeting summary already has content from the rolling
    # summary (saved by BotEngine.stop_meeting).
    transcript_source = (meeting.transcript or "").strip()
    if not transcript_source and meeting.summary and meeting.summary.content:
        transcript_source = meeting.summary.content
    summary_payload = await generator.generate(transcript_source)

    summary_dir = Path(settings.summary_dir).resolve()
    pdf_path, docx_path, pdf_bytes, docx_bytes = await anyio.to_thread.run_sync(
        _export_report_artifacts,
        generator,
        summary_payload,
        meeting_info,
        summary_dir,
        meeting.id,
    )

    report = meeting.summary
    if report is None:
        report = MeetingSummary(meeting_id=meeting.id)
        db.add(report)
        meeting.summary = report

    report.content = str(summary_payload.get("content", ""))
    report.key_points = serialize_summary_items(summary_payload.get("key_points", []))
    report.action_items = serialize_summary_items(summary_payload.get("action_items", []))
    report.decisions = serialize_summary_items(summary_payload.get("decisions", []))
    report.pdf_path = str(pdf_path)
    report.docx_path = str(docx_path)

    provider_configured = False
    is_configured = getattr(sender, "is_configured", None)
    if callable(is_configured):
        provider_configured = bool(is_configured())

    email_sent = False
    if provider_configured:
        email_sent = await sender.send_summary_email(
            to_email=current_user.email,
            meeting_info=meeting_info,
            summary=summary_payload,
            pdf_bytes=pdf_bytes,
            docx_bytes=docx_bytes,
        )

    report.email_delivery_status = (
        "sent" if email_sent else ("failed" if provider_configured else "skipped")
    )
    report.email_delivered_at = _utcnow() if email_sent else None

    usage_record = await upsert_usage_record(db=db, meeting=meeting)
    await db.flush()
    return report, usage_record


async def finalize_meeting_artifacts_for_meeting_id(
    meeting_id,
    user_email: str,
    settings: Any,
) -> None:
    """Run report finalization after the stop response using a fresh DB session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Meeting)
            .options(joinedload(Meeting.summary), joinedload(Meeting.usage_record))
            .where(Meeting.id == meeting_id)
            .with_for_update()
        )
        meeting = result.scalar_one_or_none()
        if meeting is None:
            return

        try:
            await finalize_meeting_artifacts(
                db=db,
                meeting=meeting,
                current_user=SimpleNamespace(email=user_email),
                settings=settings,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Report finalization failed for meeting %s", meeting_id)
