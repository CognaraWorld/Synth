"""Regression tests for streamed playback timing helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

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


def test_should_cancel_output_trips_on_any_stop_flag() -> None:
    from app.core.bot_engine import BotEngine

    engine = BotEngine()
    session = MagicMock(session_id="session-1")
    session.session_end_requested = False
    session.output_stop_requested = False
    engine._ensure_session_tracking(session.session_id)

    assert engine._should_cancel_output(session) is False

    session.output_stop_requested = True
    assert engine._should_cancel_output(session) is True

    session.output_stop_requested = False
    session.session_end_requested = True
    assert engine._should_cancel_output(session) is True

    session.session_end_requested = False
    engine._interrupted[session.session_id] = True
    assert engine._should_cancel_output(session) is True


@pytest.mark.asyncio
async def test_stop_meeting_waits_for_processing_lock_before_cleanup() -> None:
    from app.core.bot_engine import BotEngine
    from app.meeting.session import MeetingSession, SessionState

    engine = BotEngine()
    session = MeetingSession(
        meeting_id="meeting-1",
        agent_config={"agent_name": "Synth", "persona_id": "general"},
    )
    session.transition(SessionState.JOINING)
    session.transition(SessionState.LISTENING)
    session.context_manager.flush_remaining_embeddings = MagicMock()
    session.context_manager.raw_buffer.get_full_text = MagicMock(return_value="Alice: hi")
    session.context_manager.rolling_summary.get_summary = MagicMock(return_value="")

    engine.sessions[session.session_id] = session
    engine._ensure_session_tracking(session.session_id)
    engine._last_response_time[session.session_id] = 123.0

    lock = engine._processing_lock[session.session_id]
    await lock.acquire()

    stop_task = asyncio.create_task(engine.stop_meeting(session.session_id))
    await asyncio.sleep(0.05)

    assert stop_task.done() is False
    assert session.session_id in engine.sessions
    assert session.session_id in engine._last_response_time

    lock.release()
    result = await stop_task

    assert result["transcript"] == "Alice: hi"
    assert session.session_id not in engine.sessions
    assert session.session_id not in engine._last_response_time
    assert session.session_id not in engine._interrupted
