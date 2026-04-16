"""In-process meeting latency percentile store."""

from __future__ import annotations

import pytest

from app.observability.meeting_latency_store import (
    record_from_marks,
    reset_for_tests,
    snapshot_percentiles,
)


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    reset_for_tests()
    yield
    reset_for_tests()


def test_record_and_snapshot_percentiles() -> None:
    for _ in range(20):
        record_from_marks(
            [
                ("a", 0.0),
                ("b", 10.0),
                ("c", 40.0),
            ],
        )
    snap = snapshot_percentiles()
    edge = "a->b"
    assert edge in snap
    assert snap[edge]["n"] == 20
    assert snap[edge]["p50_ms"] == 10.0
    assert snap[edge]["p95_ms"] >= 10.0
