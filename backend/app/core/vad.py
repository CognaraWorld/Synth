"""Silero Voice Activity Detection (VAD) wrapper.

Provides real-time speech detection on incoming audio frames to determine
when a meeting participant is speaking vs. silent. Used by the bot engine
to segment audio before passing to the STT pipeline.

Phase 2 implementation.
"""

from __future__ import annotations

import time

import numpy as np
import torch


class VoiceActivityDetector:
    """Wrapper around the Silero VAD model for streaming audio.

    Processes raw audio frames and returns whether speech is detected,
    enabling the pipeline to collect speech segments for transcription.

    Attributes:
        sample_rate: Audio sample rate in Hz (default 16000).
        threshold: Confidence threshold for speech detection (0.0-1.0).
    """

    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5) -> None:
        """Initialize the VAD model.

        Args:
            sample_rate: Audio sample rate in Hz. Silero supports 8000 and 16000.
            threshold: Confidence threshold above which a frame is classified
                as speech. Higher values reduce false positives.
        """
        if sample_rate not in (8000, 16000):
            raise ValueError(
                f"Silero VAD only supports 8000 and 16000 Hz, got {sample_rate}"
            )

        self.sample_rate = sample_rate
        self.threshold = threshold

        # Expected frame sizes: 512 samples at 16kHz (32ms), 256 samples at 8kHz
        self._expected_frame_size = 512 if sample_rate == 16000 else 256

        # Speech segment tracking
        self._is_speech_active: bool = False
        self._speech_start_time: float | None = None
        self._speech_end_time: float | None = None

        # Load Silero VAD model via torch.hub
        self._model, _utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )

    @property
    def is_speech_active(self) -> bool:
        """Whether we are currently inside a speech segment."""
        return self._is_speech_active

    @property
    def speech_start_time(self) -> float | None:
        """Monotonic timestamp when the current speech segment started.

        Returns None if no speech segment is active.
        """
        return self._speech_start_time

    @property
    def speech_end_time(self) -> float | None:
        """Monotonic timestamp when the last speech segment ended.

        Returns None if no speech segment has ended yet.
        """
        return self._speech_end_time

    def process_audio_frame(self, frame: np.ndarray) -> bool:
        """Process a single audio frame and detect speech.

        Args:
            frame: Raw audio samples as a numpy array (float32, mono).
                Expected length is 512 samples at 16kHz or 256 samples at 8kHz.

        Returns:
            True if speech is detected in the frame, False otherwise.
        """
        # Ensure the frame is float32
        if frame.dtype != np.float32:
            frame = frame.astype(np.float32)

        # Ensure correct frame length — pad or truncate if necessary
        if len(frame) != self._expected_frame_size:
            if len(frame) < self._expected_frame_size:
                frame = np.pad(
                    frame, (0, self._expected_frame_size - len(frame))
                )
            else:
                frame = frame[: self._expected_frame_size]

        # Convert to torch tensor and run through the model
        tensor = torch.from_numpy(frame)
        confidence = self._model(tensor, self.sample_rate).item()

        speech_detected = confidence > self.threshold

        # Track speech segment boundaries
        now = time.monotonic()
        if speech_detected and not self._is_speech_active:
            # Speech just started
            self._is_speech_active = True
            self._speech_start_time = now
        elif not speech_detected and self._is_speech_active:
            # Speech just ended
            self._is_speech_active = False
            self._speech_end_time = now

        return speech_detected

    def reset(self) -> None:
        """Reset the VAD internal state.

        Should be called between separate audio streams or meeting sessions
        to clear any accumulated hidden state in the model.
        """
        self._model.reset_states()
        self._is_speech_active = False
        self._speech_start_time = None
        self._speech_end_time = None
