"""Shared helpers for persisted report fields and API-facing report payloads."""

from __future__ import annotations

import json
from typing import Any


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


def build_embedded_summary_payload(value: Any) -> dict[str, Any]:
    """Convert a meeting summary ORM object into a safe API payload."""
    pdf_path = getattr(value, "pdf_path", None)
    docx_path = getattr(value, "docx_path", None)
    summary_id = getattr(value, "id")
    return {
        "id": summary_id,
        "content": getattr(value, "content"),
        "key_points": getattr(value, "key_points", []),
        "action_items": getattr(value, "action_items", []),
        "decisions": getattr(value, "decisions", []),
        "email_delivery_status": getattr(value, "email_delivery_status", "pending"),
        "email_delivered_at": getattr(value, "email_delivered_at", None),
        "has_pdf": bool(pdf_path),
        "has_docx": bool(docx_path),
        "pdf_download_path": (
            f"/api/reports/{summary_id}/download/pdf" if pdf_path else None
        ),
        "docx_download_path": (
            f"/api/reports/{summary_id}/download/docx" if docx_path else None
        ),
        "created_at": getattr(value, "created_at"),
    }
