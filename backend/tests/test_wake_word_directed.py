"""Tests for is_directed_at_other (third-party addressing)."""

from __future__ import annotations


def test_directed_at_named_participant() -> None:
    from app.utils.wake_word import is_directed_at_other

    assert is_directed_at_other(
        "Sarah, what do you think about the timeline?",
        bot_names=("Nova",),
        known_participants=frozenset({"Sarah", "Bob"}),
    )


def test_directed_at_bot_name_not_other() -> None:
    from app.utils.wake_word import is_directed_at_other

    assert not is_directed_at_other(
        "Nova, can you summarize the action items?",
        bot_names=("Nova",),
        known_participants=frozenset({"Sarah"}),
    )


def test_everyone_not_other() -> None:
    from app.utils.wake_word import is_directed_at_other

    assert not is_directed_at_other(
        "Everyone, what do you think?",
        bot_names=("Synth",),
    )


def test_no_directed_pattern() -> None:
    from app.utils.wake_word import is_directed_at_other

    assert not is_directed_at_other(
        "What do you think about the budget?",
        bot_names=("Nova",),
    )
