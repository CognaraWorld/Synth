"""Regression test: live_control._utcnow() must return a naive datetime.

The live_sessions, meetings, and operator_instructions tables all use
TIMESTAMP WITHOUT TIME ZONE columns. asyncpg raises DataError on inserts
when an offset-aware datetime is passed for those columns:

    invalid input for query argument $N: ...
    (can't subtract offset-naive and offset-aware datetimes)

Previously _utcnow() returned datetime.now(timezone.utc), which fired
this error on every transcript webhook. The resulting rollback meant
last_transcript_at never persisted, the UI live-session poll saw a
stale record, and the transcript feed froze.

The contract: _utcnow() must return a naive datetime representing the
current UTC instant (tzinfo stripped).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_utcnow_returns_naive_datetime() -> None:
    from app.meeting.live_control import _utcnow

    result = _utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is None, (
        f"_utcnow() returned tz-aware datetime (tzinfo={result.tzinfo!r}); "
        "asyncpg will reject this on every live_sessions INSERT and the "
        "transcript feed will stop updating in the UI."
    )


def test_utcnow_is_close_to_utc() -> None:
    """The naive value must represent UTC, not local time — otherwise
    last_transcript_at would drift by the local TZ offset."""
    from app.meeting.live_control import _utcnow

    result = _utcnow()
    expected = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = abs((result - expected).total_seconds())
    assert delta < 5, (
        f"_utcnow() is not UTC — drifted by {delta}s from naive UTC now. "
        "Don't use datetime.now() (local time); use "
        "datetime.now(timezone.utc).replace(tzinfo=None)."
    )
