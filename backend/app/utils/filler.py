"""Filler response manager.

Manages pre-synthesized filler audio responses that are played while
the LLM processes a question. Reduces perceived latency by giving
an immediate acknowledgment before the full answer is ready.

Phase 3 implementation.
"""

from __future__ import annotations

import random


FILLER_PHRASES: list[str] = [
    "Let me think about that for a moment.",
    "That's a great question, give me a second.",
    "One moment while I look into that.",
    "Hmm, let me consider that.",
    "Sure, let me pull that up.",
    "Good question, let me check.",
    "Bear with me for just a second.",
    "Let me find that information for you.",
]
"""Pre-defined filler phrases spoken while the LLM generates a response."""


class FillerManager:
    """Manages filler audio responses for latency masking.

    Pre-synthesizes filler phrases into audio on initialization so they
    can be played instantly when needed, without waiting for TTS.

    Attributes:
        phrases: List of filler phrase strings.
        cache: Pre-synthesized audio bytes keyed by phrase.
    """

    def __init__(self) -> None:
        """Initialize the filler manager and pre-synthesize audio.

        Pre-generates audio for all filler phrases so they can be
        served instantly without TTS latency.
        """
        self.phrases = FILLER_PHRASES
        self._cache: dict[str, bytes] = {}
        # TODO: Initialize TTS and pre-synthesize all filler phrases
        raise NotImplementedError("Phase 3 implementation")

    def get_random_filler(self) -> bytes:
        """Return a random pre-synthesized filler audio response.

        Selects a random filler phrase and returns its pre-generated
        audio bytes for immediate playback.

        Returns:
            Raw audio bytes (PCM format) of a random filler phrase.
        """
        # TODO: Select random phrase, return cached audio bytes
        raise NotImplementedError("Phase 3 implementation")
