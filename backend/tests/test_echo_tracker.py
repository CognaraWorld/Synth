"""Tests for app.utils.echo_tracker."""

from __future__ import annotations

import pytest

from app.utils import echo_tracker


@pytest.fixture(autouse=True)
def _clear_echo_state() -> None:
    """Isolate tests from shared module-level storage."""
    with echo_tracker._lock:
        echo_tracker._recent_output.clear()
    yield
    with echo_tracker._lock:
        echo_tracker._recent_output.clear()


def test_record_and_is_echo_substring() -> None:
    echo_tracker.record("bot-a", "The quarterly revenue was up twelve percent.")
    assert echo_tracker.is_echo("bot-a", "the quarterly revenue was up twelve percent.")
    assert not echo_tracker.is_echo("bot-a", "short")


def test_record_ignores_empty() -> None:
    echo_tracker.record("", "hello")
    echo_tracker.record("bot-b", "")
    assert not echo_tracker.is_echo("bot-b", "hello there everyone")


def test_cleanup_removes_bot() -> None:
    echo_tracker.record("bot-c", "We should ship the feature tomorrow.")
    assert echo_tracker.is_echo("bot-c", "ship the feature tomorrow")
    echo_tracker.cleanup("bot-c")
    assert not echo_tracker.is_echo("bot-c", "ship the feature tomorrow")


def test_different_bots_isolated() -> None:
    echo_tracker.record("bot-1", "alpha beta gamma")
    assert echo_tracker.is_echo("bot-1", "alpha beta gamma delta")
    assert not echo_tracker.is_echo("bot-2", "alpha beta gamma delta")
