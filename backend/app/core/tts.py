"""Kokoro Text-to-Speech (TTS) wrapper.

Converts text responses into natural-sounding audio bytes that can be
streamed back into the meeting via the Recall.ai bot. Also generates
filler responses ("Let me think about that...") to reduce perceived latency.

Phase 3 implementation.
"""

from __future__ import annotations


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
        voice: str = "default",
        sample_rate: int = 24000,
        speed: float = 1.0,
    ) -> None:
        """Initialize the Kokoro TTS engine.

        Args:
            voice: Voice profile to use for synthesis.
            sample_rate: Desired output sample rate in Hz.
            speed: Speech speed multiplier. Values > 1.0 are faster.
        """
        self.voice = voice
        self.sample_rate = sample_rate
        self.speed = speed
        # TODO: Load Kokoro TTS model and voice profile
        raise NotImplementedError("Phase 3 implementation")

    def synthesize(self, text: str) -> bytes:
        """Convert text to speech audio.

        Args:
            text: The text to synthesize into audio.

        Returns:
            Raw audio bytes (PCM format) suitable for streaming into
            the meeting via Recall.ai.
        """
        # TODO: Run Kokoro synthesis, return PCM audio bytes
        raise NotImplementedError("Phase 3 implementation")

    def get_filler_response(self) -> bytes:
        """Generate a random filler phrase as audio.

        Used to reduce perceived latency while the LLM processes a
        question. Randomly selects from pre-defined filler phrases.

        Returns:
            Raw audio bytes of a synthesized filler phrase.
        """
        # TODO: Pick random filler phrase, synthesize, and return audio bytes
        raise NotImplementedError("Phase 3 implementation")
