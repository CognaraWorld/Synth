"""Whisper Speech-to-Text (STT) wrapper.

Converts audio segments into text transcriptions using faster-whisper.
Produces structured TranscriptSegment objects with metadata including
timestamps, speaker labels, and confidence scores.

Phase 2 implementation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from faster_whisper import WhisperModel


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


@dataclass
class TimestampedWord:
    """A single word with its precise timing information.

    Attributes:
        word: The transcribed word.
        start: Start time in seconds relative to the audio segment.
        end: End time in seconds relative to the audio segment.
        probability: Model confidence for this word.
    """

    word: str
    start: float
    end: float
    probability: float


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
        model_size: str = "large-v3",
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

        # Load faster-whisper model with CTranslate2 backend.
        # int8 compute type for M4 Max CPU — fast and memory-efficient.
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type="int8",
        )

    def transcribe(self, audio_segment: np.ndarray) -> TranscriptSegment:
        """Transcribe an audio segment into text.

        Args:
            audio_segment: Audio data as a numpy array (float32, mono, 16kHz).
                Should contain a complete speech segment as detected by VAD.

        Returns:
            A TranscriptSegment with the transcribed text, timestamp,
            and confidence score.
        """
        # Ensure float32 dtype
        if audio_segment.dtype != np.float32:
            audio_segment = audio_segment.astype(np.float32)

        segments_iter, _info = self._model.transcribe(
            audio_segment,
            language=self.language,
            beam_size=5,
            vad_filter=False,  # We handle VAD externally
        )

        # Collect all segments and compute aggregate text and confidence
        texts: list[str] = []
        confidences: list[float] = []

        for segment in segments_iter:
            text = segment.text.strip()
            if text:
                texts.append(text)
                confidences.append(segment.avg_logprob)

        full_text = " ".join(texts)

        # Convert average log-probability to a 0-1 confidence score.
        # Whisper log-probs are negative; typical range is roughly -1.0 to 0.0.
        # We clamp exp(avg_logprob) to [0, 1] as an approximate confidence.
        if confidences:
            avg_logprob = sum(confidences) / len(confidences)
            avg_confidence = max(0.0, min(1.0, math.exp(avg_logprob)))
        else:
            avg_confidence = 0.0

        return TranscriptSegment(
            text=full_text,
            timestamp=datetime.utcnow(),
            confidence=avg_confidence,
        )

    def transcribe_with_timestamps(
        self, audio_segment: np.ndarray
    ) -> list[TimestampedWord]:
        """Transcribe an audio segment with word-level timestamps.

        Args:
            audio_segment: Audio data as a numpy array (float32, mono, 16kHz).

        Returns:
            A list of TimestampedWord objects with precise timing for each word.
        """
        if audio_segment.dtype != np.float32:
            audio_segment = audio_segment.astype(np.float32)

        segments_iter, _info = self._model.transcribe(
            audio_segment,
            language=self.language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=False,
        )

        words: list[TimestampedWord] = []
        for segment in segments_iter:
            if segment.words:
                for w in segment.words:
                    words.append(
                        TimestampedWord(
                            word=w.word.strip(),
                            start=w.start,
                            end=w.end,
                            probability=w.probability,
                        )
                    )

        return words
