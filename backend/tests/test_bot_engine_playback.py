"""Regression tests for streamed playback timing helpers."""

from __future__ import annotations

import pytest


def test_enqueue_playback_chunk_starts_at_first_send() -> None:
    from app.core.bot_engine import BotEngine

    total_playback, playback_started_at = BotEngine._enqueue_playback_chunk(
        0.0,
        None,
        b"\x00" * 48000,
        now=10.0,
    )

    assert total_playback == pytest.approx(1.0)
    assert playback_started_at == 10.0

    total_playback, playback_started_at = BotEngine._enqueue_playback_chunk(
        total_playback,
        playback_started_at,
        b"\x00" * 24000,
        now=14.0,
    )

    assert total_playback == pytest.approx(1.5)
    assert playback_started_at == 10.0


def test_remaining_playback_time_uses_first_enqueue_timestamp() -> None:
    from app.core.bot_engine import BotEngine

    assert BotEngine._remaining_playback_time(2.0, 10.0, now=11.25) == pytest.approx(0.75)
    assert BotEngine._remaining_playback_time(2.0, None, now=11.25) == 0.0
