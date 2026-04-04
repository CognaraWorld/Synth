"""Tests for the Phase 3 audio pipeline components.

Tests are organized into four groups:

1. Wake Word Detection  -- pure string logic, no models, fast
2. Raw Transcript Buffer -- in-memory buffer operations, no models, fast
3. Filler Manager       -- phrase selection, no models, fast
4. Integration (VAD/STT) -- requires ML models, marked ``@pytest.mark.slow``

Run fast tests only::

    pytest tests/test_audio_pipeline.py -m "not slow"

Run everything (needs models downloaded)::

    pytest tests/test_audio_pipeline.py
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Wake Word Detection
# ---------------------------------------------------------------------------


class TestWakeWordDetection:
    """Tests for ``app.utils.wake_word.detect``."""

    def test_wake_word_basic(self) -> None:
        """Standard 'Hey Assistant, <question>' pattern extracts the question."""
        from app.utils.wake_word import detect

        detected, question = detect("Hey Assistant, what is the revenue?")
        assert detected is True
        assert question == "what is the revenue?"

    def test_wake_word_case_insensitive(self) -> None:
        """Detection is case-insensitive across the whole wake phrase."""
        from app.utils.wake_word import detect

        detected, question = detect("hey assistant tell me")
        assert detected is True
        assert question == "tell me"

    def test_wake_word_just_name(self) -> None:
        """Bare 'Assistant' without prefix should NOT trigger (prevents false positives)."""
        from app.utils.wake_word import detect

        detected, question = detect("Assistant, what time is it?")
        assert detected is False

    def test_wake_word_phonetic_variant(self) -> None:
        """STT mishearings like 'hey assistance' should still trigger."""
        from app.utils.wake_word import detect

        detected, question = detect("Hey assistance, what time is it?")
        assert detected is True
        assert question == "what time is it?"

    def test_wake_word_not_found(self) -> None:
        """Returns (False, '') when the wake word is absent."""
        from app.utils.wake_word import detect

        detected, question = detect("Let's discuss the budget")
        assert detected is False
        assert question == ""

    def test_wake_word_at_end(self) -> None:
        """Wake word at the end of input yields an empty question string."""
        from app.utils.wake_word import detect

        detected, question = detect("Hey Assistant")
        assert detected is True
        assert question == ""

    def test_wake_word_with_comma(self) -> None:
        """Comma between 'Hey,' and 'Assistant,' is handled gracefully."""
        from app.utils.wake_word import detect

        detected, question = detect("Hey, Assistant, what's up?")
        assert detected is True
        assert question == "what's up?"


# ---------------------------------------------------------------------------
# Raw Transcript Buffer
# ---------------------------------------------------------------------------


class TestRawTranscriptBuffer:
    """Tests for ``app.context.raw_buffer.RawTranscriptBuffer``."""

    def test_buffer_append_and_retrieve(self) -> None:
        """Appended entries are returned by ``get_recent``."""
        from app.context.raw_buffer import RawTranscriptBuffer

        buf = RawTranscriptBuffer(max_minutes=10)
        now = datetime.now(timezone.utc)

        buf.append("Hello, welcome to the meeting.", timestamp=now)
        buf.append("Thanks, glad to be here.", timestamp=now + timedelta(seconds=5))

        recent = buf.get_recent(minutes=5)
        assert "Hello, welcome to the meeting." in recent
        assert "Thanks, glad to be here." in recent

    def test_buffer_time_window(self) -> None:
        """``get_recent`` respects the requested time window.

        Entries older than the requested window should be excluded while
        entries within the window are included.
        """
        from app.context.raw_buffer import RawTranscriptBuffer

        buf = RawTranscriptBuffer(max_minutes=10)
        now = datetime.now(timezone.utc)

        # Entry from 8 minutes ago -- outside a 5-minute window
        buf.append("Old entry", timestamp=now - timedelta(minutes=8))
        # Entry from 2 minutes ago -- inside a 5-minute window
        buf.append("Recent entry", timestamp=now - timedelta(minutes=2))

        recent = buf.get_recent(minutes=5)
        assert "Old entry" not in recent
        assert "Recent entry" in recent

    def test_buffer_clear(self) -> None:
        """``clear`` empties the buffer completely."""
        from app.context.raw_buffer import RawTranscriptBuffer

        buf = RawTranscriptBuffer(max_minutes=10)
        buf.append("Something important", timestamp=datetime.now(timezone.utc))

        buf.clear()

        recent = buf.get_recent(minutes=10)
        assert recent == "" or recent.strip() == ""

    def test_buffer_auto_prune(self) -> None:
        """Entries older than ``max_minutes`` are automatically pruned.

        After adding an entry that exceeds the max window and then
        triggering a read, the stale entry should be gone.
        """
        from app.context.raw_buffer import RawTranscriptBuffer

        buf = RawTranscriptBuffer(max_minutes=5)
        now = datetime.now(timezone.utc)

        # Entry from 10 minutes ago -- well past the 5-minute max
        buf.append("Very old entry", timestamp=now - timedelta(minutes=10))
        # Fresh entry
        buf.append("Fresh entry", timestamp=now)

        # Reading should trigger pruning of the old entry
        recent = buf.get_recent(minutes=5)
        assert "Very old entry" not in recent
        assert "Fresh entry" in recent

    def test_buffer_thread_safety(self) -> None:
        """Concurrent appends from multiple threads do not corrupt the buffer.

        Launches several threads that each append a known number of entries.
        After all threads complete, the total entry count must match
        the expected sum.
        """
        from app.context.raw_buffer import RawTranscriptBuffer

        buf = RawTranscriptBuffer(max_minutes=10)
        num_threads = 8
        entries_per_thread = 50
        barrier = threading.Barrier(num_threads)

        def writer(thread_id: int) -> None:
            barrier.wait()  # synchronize start for maximum contention
            for i in range(entries_per_thread):
                buf.append(
                    f"Thread-{thread_id} entry-{i}",
                    timestamp=datetime.now(timezone.utc),
                )

        threads = [
            threading.Thread(target=writer, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        recent = buf.get_recent(minutes=10)
        expected_total = num_threads * entries_per_thread
        # Each entry is a separate line/segment -- count occurrences of "entry-"
        actual_count = recent.count("entry-")
        assert actual_count == expected_total, (
            f"Expected {expected_total} entries but found {actual_count}. "
            "Buffer may have a thread-safety issue."
        )


# ---------------------------------------------------------------------------
# Filler Manager
# ---------------------------------------------------------------------------


class TestFillerManager:
    """Tests for ``app.utils.filler.FillerManager``."""

    def test_filler_random(self) -> None:
        """``get_random_filler`` returns one of the known filler phrases."""
        from app.utils.filler import CATEGORY_FILLERS, FillerManager

        manager = FillerManager()
        all_phrases = manager._all_phrases()

        # Populate cache with fake audio
        manager._cache = {phrase: b"fake_audio" for phrase in all_phrases}

        result = manager.get_random_filler()
        assert result in all_phrases

    def test_filler_returns_string(self) -> None:
        """Each phrase across all categories is a non-empty string."""
        from app.utils.filler import CATEGORY_FILLERS

        for category, phrases in CATEGORY_FILLERS.items():
            for phrase in phrases:
                assert isinstance(phrase, str)
                assert len(phrase) > 0

    def test_filler_phrases_are_unique(self) -> None:
        """All filler phrases across all categories are distinct."""
        from app.utils.filler import CATEGORY_FILLERS

        all_phrases = []
        for phrases in CATEGORY_FILLERS.values():
            all_phrases.extend(phrases)
        assert len(all_phrases) == len(set(all_phrases))

    def test_filler_manager_attributes_after_init(self) -> None:
        """A FillerManager has the expected attributes after construction."""
        from app.utils.filler import FillerManager

        manager = FillerManager()

        assert isinstance(manager._cache, dict)
        assert isinstance(manager._mp3_cache, dict)


# ---------------------------------------------------------------------------
# Integration Tests (require ML models -- slow)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestVADIntegration:
    """Integration tests for ``app.core.vad.VoiceActivityDetector``.

    These tests instantiate the Silero VAD model and require it to be
    downloadable (internet access or cached). They are slow and should
    be excluded from CI fast-feedback loops.
    """

    def test_vad_with_silence(self) -> None:
        """VAD returns False for a frame of pure digital silence."""
        from app.core.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(sample_rate=16000, threshold=0.5)

        # 512 samples of silence (~32 ms at 16 kHz)
        silent_frame = np.zeros(512, dtype=np.float32)
        result = vad.process_audio_frame(silent_frame)

        assert result is False, "VAD should not detect speech in a silent frame"

    def test_vad_with_noise(self) -> None:
        """VAD processes a noisy frame without raising exceptions.

        Random noise is not speech, but the test primarily verifies that
        the model handles arbitrary input gracefully. The detection result
        may vary so we only assert the return type.
        """
        from app.core.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(sample_rate=16000, threshold=0.5)

        rng = np.random.default_rng(seed=42)
        noise_frame = rng.uniform(-1.0, 1.0, size=512).astype(np.float32)
        result = vad.process_audio_frame(noise_frame)

        assert isinstance(result, bool), "VAD must return a boolean"

    def test_vad_reset(self) -> None:
        """``reset`` clears internal state without raising exceptions."""
        from app.core.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(sample_rate=16000, threshold=0.5)

        # Process a frame then reset -- should not raise
        silent_frame = np.zeros(512, dtype=np.float32)
        vad.process_audio_frame(silent_frame)
        vad.reset()

        # Process again after reset -- state should be clean
        result = vad.process_audio_frame(silent_frame)
        assert isinstance(result, bool)


@pytest.mark.slow
class TestSTTIntegration:
    """Integration tests for ``app.core.stt.SpeechToText``.

    Requires the faster-whisper model to be downloadable.
    """

    def test_stt_transcribe_silence(self) -> None:
        """STT produces a TranscriptSegment from a silent audio chunk.

        The transcribed text may be empty or contain only whitespace,
        but the operation should complete without error.
        """
        from app.core.stt import SpeechToText, TranscriptSegment

        stt = SpeechToText(model_size="tiny", language="en", device="cpu")

        # 1 second of silence at 16 kHz
        silent_audio = np.zeros(16000, dtype=np.float32)
        segment = stt.transcribe(silent_audio)

        assert isinstance(segment, TranscriptSegment)
        assert isinstance(segment.text, str)
        assert 0.0 <= segment.confidence <= 1.0


@pytest.mark.slow
class TestFullPipelineIntegration:
    """End-to-end integration test: synthetic audio through VAD then STT."""

    def test_full_pipeline(self) -> None:
        """Run synthetic audio through VAD and, if speech detected, through STT.

        Generates a sine-wave tone (440 Hz) which may or may not trigger
        the VAD. The test verifies that the pipeline executes without errors
        regardless of detection outcome.
        """
        from app.core.stt import SpeechToText, TranscriptSegment
        from app.core.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(sample_rate=16000, threshold=0.5)
        stt = SpeechToText(model_size="tiny", language="en", device="cpu")

        # Generate a 440 Hz sine wave (1 second at 16 kHz)
        sample_rate = 16000
        t = np.linspace(0, 1.0, sample_rate, endpoint=False, dtype=np.float32)
        tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        # Process in 512-sample frames
        frame_size = 512
        speech_detected = False
        for start in range(0, len(tone) - frame_size + 1, frame_size):
            frame = tone[start : start + frame_size]
            if vad.process_audio_frame(frame):
                speech_detected = True

        # If VAD triggered, attempt transcription on the full audio
        if speech_detected:
            segment = stt.transcribe(tone)
            assert isinstance(segment, TranscriptSegment)
            assert isinstance(segment.text, str)

        # Pipeline completed without errors -- pass regardless of detection
        vad.reset()
