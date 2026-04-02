"""Whisper Speech-to-Text (STT) wrapper.

Converts audio segments into text transcriptions using faster-whisper.
Produces structured TranscriptSegment objects with metadata including
timestamps, speaker labels, and confidence scores.

Phase 2 implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class TranscriptSegment:
    """A single segment of transcribed speech.

    Attributes:
        text: The transcribed text content.
        timestamp: When this segment was captured.
        speaker: Speaker label or identifier (e.g., "Speaker 1").
        confidence: Model confidence score between 0.0 and 1.0.
    """

    text: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    speaker: str = "unknown"
    confidence: float = 0.0


class SpeechToText:
    """Wrapper around faster-whisper for real-time transcription.

    Accepts audio segments collected by the VAD and produces text
    transcriptions with associated metadata.

    Attributes:
        model_size: Whisper model size (tiny, base, small, medium, large-v3).
        language: Target language code (e.g., "en").
        device: Compute device ("cpu" or "cuda").
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = "en",
        device: str = "cpu",
    ) -> None:
        """Initialize the Whisper STT model.

        Args:
            model_size: Whisper model variant to load. Larger models are more
                accurate but slower. Options: tiny, base, small, medium, large-v3.
            language: ISO 639-1 language code for transcription.
            device: Compute device for inference.
        """
        self.model_size = model_size
        self.language = language
        self.device = device
        # TODO: Load faster-whisper model with CTranslate2 backend
        raise NotImplementedError("Phase 2 implementation")

    def transcribe(self, audio_segment: np.ndarray) -> TranscriptSegment:
        """Transcribe an audio segment into text.

        Args:
            audio_segment: Audio data as a numpy array (float32, mono, 16kHz).
                Should contain a complete speech segment as detected by VAD.

        Returns:
            A TranscriptSegment with the transcribed text, timestamp,
            and confidence score.
        """
        # TODO: Run faster-whisper inference, extract text and confidence
        # TODO: Apply speaker diarization label if available
        raise NotImplementedError("Phase 2 implementation")
