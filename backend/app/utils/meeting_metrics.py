"""Lightweight per-question latency markers for observability.

Logs structured timing between major pipeline stages (filler, context,
web search, LLM stream, TTS) so operators can grep logs or ship them to
metrics backends.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class QuestionStageTimer:
    """Collect monotonic timestamps for a single Q&A turn."""

    __slots__ = ("_t0", "marks", "preview", "session_prefix")

    def __init__(self, session_id: str, question_preview: str) -> None:
        self._t0 = time.perf_counter()
        self.marks: list[tuple[str, float]] = []
        self.session_prefix = session_id[:8] if session_id else "?"
        self.preview = (question_preview or "")[:80].replace("\n", " ")

    def mark(self, stage: str) -> None:
        """Record *stage* at elapsed ms since construction."""
        elapsed_ms = (time.perf_counter() - self._t0) * 1000.0
        self.marks.append((stage, elapsed_ms))

    def log_summary(self, extra: dict[str, Any] | None = None) -> None:
        """Emit one INFO line with cumulative ms per stage."""
        parts = [f"{name}={ms:.0f}ms" for name, ms in self.marks]
        suffix = ""
        if extra:
            suffix = " " + " ".join(f"{k}={v}" for k, v in extra.items())
        logger.info(
            "question_latency session=%s q=%r %s%s",
            self.session_prefix,
            self.preview,
            " ".join(parts),
            suffix,
        )
        if len(self.marks) >= 2:
            try:
                from app.observability.meeting_latency_store import record_from_marks

                record_from_marks(self.marks)
            except Exception:
                logger.debug("meeting latency store failed", exc_info=True)
