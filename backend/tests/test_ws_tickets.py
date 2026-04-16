"""Tests for the single-use WebSocket ticket store."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from app.core import ws_tickets


@pytest.fixture(autouse=True)
def _reset_ticket_state():
    ws_tickets.reset_for_tests()
    yield
    ws_tickets.reset_for_tests()


def test_issued_ticket_validates_for_bound_user() -> None:
    user_id = uuid4()
    ticket, expires_in = ws_tickets.issue_ticket(user_id)

    assert ticket, "issue_ticket must return a non-empty ticket"
    assert expires_in == ws_tickets.TICKET_TTL_SECONDS
    assert ws_tickets.consume_ticket(ticket) == user_id


def test_ticket_is_single_use() -> None:
    ticket, _ = ws_tickets.issue_ticket(uuid4())
    assert ws_tickets.consume_ticket(ticket) is not None
    # Second consume must fail — single-use is the whole point.
    assert ws_tickets.consume_ticket(ticket) is None


def test_unknown_ticket_rejected() -> None:
    assert ws_tickets.consume_ticket("definitely-not-a-ticket") is None
    assert ws_tickets.consume_ticket("") is None


def test_expired_ticket_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ticket older than TICKET_TTL_SECONDS must not validate."""
    real_time = time.time

    # Issue at t=0
    monkeypatch.setattr(ws_tickets.time, "time", lambda: 1_000_000.0)
    ticket, _ = ws_tickets.issue_ticket(uuid4())

    # Consume well past the TTL
    monkeypatch.setattr(
        ws_tickets.time,
        "time",
        lambda: 1_000_000.0 + ws_tickets.TICKET_TTL_SECONDS + 1,
    )
    assert ws_tickets.consume_ticket(ticket) is None

    # Restore (pytest will do it anyway via monkeypatch, but be explicit)
    monkeypatch.setattr(ws_tickets.time, "time", real_time)


def test_tickets_are_unique_per_call() -> None:
    user_id = uuid4()
    t1, _ = ws_tickets.issue_ticket(user_id)
    t2, _ = ws_tickets.issue_ticket(user_id)
    assert t1 != t2


def test_consume_does_not_leak_across_users() -> None:
    alice, bob = uuid4(), uuid4()
    alice_ticket, _ = ws_tickets.issue_ticket(alice)
    bob_ticket, _ = ws_tickets.issue_ticket(bob)

    assert ws_tickets.consume_ticket(alice_ticket) == alice
    assert ws_tickets.consume_ticket(bob_ticket) == bob
