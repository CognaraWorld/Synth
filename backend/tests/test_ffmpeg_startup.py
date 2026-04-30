"""Regression tests: ffmpeg availability is verified loudly at startup.

Previously, ``RecallClient.pcm_to_mp3_b64`` swallowed ``FileNotFoundError``
when ffmpeg was missing and returned an empty string. This caused the bot
to silently emit no audio in production (filler preload built an empty
cache and every TTS response converted to ``b""``) — operators got no
exception, no ERROR log, and a meeting with a mute bot.

The fixes:
1. ``check_ffmpeg_available()`` probes the binary at startup. In
   ``ENVIRONMENT=production`` it raises; otherwise it logs at ERROR.
2. ``pcm_to_mp3_b64`` upgrades the missing-ffmpeg log from WARNING to
   ERROR and only emits it once per process so we shout the first time
   a conversion fails but don't spam.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest


class TestFfmpegStartupCheck:
    def test_check_returns_true_when_pydub_can_export(self) -> None:
        from app.main import check_ffmpeg_available

        assert check_ffmpeg_available() is True

    def test_check_returns_false_when_export_raises_filenotfound(self) -> None:
        from app.main import check_ffmpeg_available

        with patch("app.main.AudioSegment") as fake_segment:
            fake_segment.return_value.export.side_effect = FileNotFoundError(
                "no ffmpeg"
            )
            assert check_ffmpeg_available() is False

    def test_check_returns_false_on_any_export_exception(self) -> None:
        from app.main import check_ffmpeg_available

        with patch("app.main.AudioSegment") as fake_segment:
            fake_segment.return_value.export.side_effect = Exception(
                "decoder bork"
            )
            assert check_ffmpeg_available() is False


class TestFfmpegLoudFailure:
    def test_pcm_to_mp3_b64_logs_at_error_when_ffmpeg_missing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from app.meeting import recall_client

        # Reset the one-shot flag so the ERROR fires for this test.
        recall_client._FFMPEG_MISSING_LOGGED = False

        # Build minimal valid PCM (10 ms of silence at 24 kHz)
        pcm_bytes = b"\x00\x00" * 240

        with patch.object(
            recall_client, "AudioSegment"
        ) as fake_segment:
            fake_segment.return_value.export.side_effect = FileNotFoundError(
                "ffmpeg not found"
            )
            with caplog.at_level(logging.ERROR, logger="app.meeting.recall_client"):
                result = recall_client.RecallClient.pcm_to_mp3_b64(pcm_bytes)

        assert result == ""
        # Must surface as ERROR (not WARNING) because the bot will be mute.
        error_records = [
            r for r in caplog.records
            if r.levelno >= logging.ERROR
            and "ffmpeg" in r.getMessage().lower()
        ]
        assert error_records, (
            "Missing ffmpeg must be logged at ERROR level so operators "
            "see it in production logs — not silently downgraded to WARNING."
        )

    def test_pcm_to_mp3_b64_one_shot_flag_prevents_log_spam(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from app.meeting import recall_client

        recall_client._FFMPEG_MISSING_LOGGED = False
        pcm_bytes = b"\x00\x00" * 240

        with patch.object(
            recall_client, "AudioSegment"
        ) as fake_segment:
            fake_segment.return_value.export.side_effect = FileNotFoundError(
                "ffmpeg not found"
            )
            with caplog.at_level(logging.ERROR, logger="app.meeting.recall_client"):
                recall_client.RecallClient.pcm_to_mp3_b64(pcm_bytes)
                recall_client.RecallClient.pcm_to_mp3_b64(pcm_bytes)
                recall_client.RecallClient.pcm_to_mp3_b64(pcm_bytes)

        ffmpeg_errors = [
            r for r in caplog.records
            if r.levelno >= logging.ERROR
            and "ffmpeg" in r.getMessage().lower()
        ]
        assert len(ffmpeg_errors) == 1, (
            f"Expected exactly one ERROR log across 3 conversion attempts; "
            f"got {len(ffmpeg_errors)}. The one-shot flag must suppress "
            f"repeats to avoid log spam."
        )
