"""In-process meeting Q&A latency store with rolling p50 / p95.

Safe for multi-threaded access (BotEngine + asyncio). Intended for
dashboards, on-call debugging, or future Prometheus export — not a
distributed metrics backend.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

_MAX_SAMPLES_PER_EDGE = 2000
_ROLLUP_EVERY_N = 50

_lock = threading.Lock()
_edge_samples: dict[str, deque[float]] = {}
_recorded_turns = 0


def _nearest_rank_percentile(sorted_vals: list[float], q: float) -> float:
    """Return *q* percentile (0..1) using nearest-rank on *sorted_vals*."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = min(n - 1, max(0, int(round(q * (n - 1)))))
    return sorted_vals[idx]


def record_from_marks(marks: list[tuple[str, float]]) -> None:
    """Record inter-stage deltas from cumulative ``QuestionStageTimer`` marks."""
    global _recorded_turns
    if len(marks) < 2:
        return
    prev_name, prev_ms = marks[0]
    with _lock:
        for name, ms in marks[1:]:
            delta = max(0.0, ms - prev_ms)
            edge = f"{prev_name}->{name}"
            bucket = _edge_samples.setdefault(edge, deque(maxlen=_MAX_SAMPLES_PER_EDGE))
            bucket.append(delta)
            prev_name, prev_ms = name, ms
        _recorded_turns += 1
        do_rollup = _recorded_turns % _ROLLUP_EVERY_N == 0
    if do_rollup:
        snap = snapshot_percentiles()
        if snap:
            logger.info("meeting_latency_rollup %s", json.dumps(snap, separators=(",", ":")))


def snapshot_percentiles() -> dict[str, Any]:
    """Return p50 / p95 / sample count per recorded edge (copy under lock)."""
    out: dict[str, Any] = {}
    with _lock:
        for edge, samples in _edge_samples.items():
            if not samples:
                continue
            vals = sorted(samples)
            out[edge] = {
                "n": len(vals),
                "p50_ms": round(_nearest_rank_percentile(vals, 0.50), 2),
                "p95_ms": round(_nearest_rank_percentile(vals, 0.95), 2),
            }
    return out


def reset_for_tests() -> None:
    """Clear all samples (unit tests only)."""
    global _recorded_turns
    with _lock:
        _edge_samples.clear()
        _recorded_turns = 0
