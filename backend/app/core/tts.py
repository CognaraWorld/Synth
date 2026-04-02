"""Kokoro Text-to-Speech (TTS) wrapper.

Converts text responses into natural-sounding audio bytes that can be
streamed back into the meeting via the Recall.ai bot. Also generates
filler responses ("Let me think about that...") to reduce perceived latency.

Phase 3 implementation.
"""

from __future__ import annotations

import io
import random
import wave

import numpy as np
from kokoro import KPipeline


class TextToSpeech:
    """Wrapper around the Kokoro TTS model for speech synthesis.

    Generates audio bytes from text, supporting both full responses
    and quick filler phrases for latency masking.

    Attributes:
        voice: Voice profile identifier.
        sample_rate: Output audio sample rate in Hz.
        speed: Speech speed multiplier (1.0 = normal).
    """

    FILLER_PHRASES: list[str] = [
        "Let me think about that for a moment.",
        "That's a great question, give me a second.",
        "One moment while I look into that.",
        "Hmm, let me consider that.",
        "Sure, let me pull that up.",
    ]

    def __init__(
        self,
        voice: str = "af_heart",
        sample_rate: int = 24000,
        speed: float = 1.0,
    ) -> None:
        """Initialize the Kokoro TTS engine.

        Args:
            voice: Voice profile to use for synthesis. Kokoro voices use
                codes like ``af_heart`` (American female) or ``am_adam``
                (American male).
            sample_rate: Desired output sample rate in Hz. Kokoro natively
                outputs at 24000 Hz.
            speed: Speech speed multiplier. Values > 1.0 are faster.
        """
        self.voice = voice
        self.sample_rate = sample_rate
        self.speed = speed

        # Initialize Kokoro pipeline — 'a' = American English
        self._pipeline = KPipeline(lang_code="a")

    def synthesize(self, text: str) -> bytes:
        """Convert text to speech audio.

        Args:
            text: The text to synthesize into audio.

        Returns:
            Raw audio bytes (PCM int16 format) suitable for streaming
            into the meeting via Recall.ai.
        """
        audio_chunks: list[np.ndarray] = []

        for _graphemes, _phonemes, audio_tensor in self._pipeline(
            text, voice=self.voice, speed=self.speed
        ):
            if audio_tensor is not None:
                # audio_tensor is a 1-D torch tensor of float32 samples
                audio_np = audio_tensor.numpy()
                audio_chunks.append(audio_np)

        if not audio_chunks:
            return b""

        # Concatenate all chunks into a single float32 array
        full_audio = np.concatenate(audio_chunks)

        # Clamp to [-1, 1] and convert to PCM int16 bytes
        full_audio = np.clip(full_audio, -1.0, 1.0)
        pcm_int16 = (full_audio * 32767).astype(np.int16)
        return pcm_int16.tobytes()

    def synthesize_to_wav(self, text: str) -> bytes:
        """Convert text to a complete WAV file.

        Args:
            text: The text to synthesize into audio.

        Returns:
            A complete WAV file as bytes with proper headers, suitable
            for saving to disk or sending over HTTP.
        """
        pcm_data = self.synthesize(text)
        if not pcm_data:
            return b""

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes per sample
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data)

        return buf.getvalue()

    def get_filler_response(self) -> bytes:
        """Generate a random filler phrase as audio.

        Used to reduce perceived latency while the LLM processes a
        question. Randomly selects from pre-defined filler phrases.

        Returns:
            Raw audio bytes of a synthesized filler phrase.
        """
        phrase = random.choice(self.FILLER_PHRASES)
        return self.synthesize(phrase)
