"""Persistence helpers for generated meeting reports and usage records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.meeting.email_sender import EmailSender
from app.meeting.summary import SummaryGenerator
from app.models.database import Meeting, MeetingSummary, UsageRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_summary_items(items: list[str] | tuple[str, ...] | None) -> str:
    """Store structured summary lists as JSON text."""
    return json.dumps([str(item) for item in (items or [])], ensure_ascii=True)


def deserialize_summary_items(raw_value: str | list[str] | None) -> list[str]:
    """Decode summary list fields stored as JSON text."""
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value if str(item).strip()]

    stripped = str(raw_value).strip()
    if not stripped:
        return []

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError:
        lines = [line.lstrip("- ").strip() for line in stripped.splitlines() if line.strip()]
        return lines or [stripped]

    if isinstance(decoded, list):
        return [str(item) for item in decoded if str(item).strip()]
    if isinstance(decoded, str) and decoded.strip():
        return [decoded.strip()]
    return []


def build_report_preview(content: str, limit: int = 180) -> str:
    """Collapse summary content into a short preview string."""
    normalized = " ".join((content or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}..."


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

    meeting_info = build_meeting_info(meeting)
    summary_payload = await generator.generate(meeting.transcript or "")

    summary_dir = Path(settings.summary_dir).resolve()
    summary_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = summary_dir / f"{meeting.id}.pdf"
    docx_path = summary_dir / f"{meeting.id}.docx"

    pdf_bytes = generator.export_pdf(summary_payload, meeting_info=meeting_info)
    docx_bytes = generator.export_docx(summary_payload, meeting_info=meeting_info)
    pdf_path.write_bytes(pdf_bytes)
    docx_path.write_bytes(docx_bytes)

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
