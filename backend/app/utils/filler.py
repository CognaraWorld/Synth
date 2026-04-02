"""Filler response manager.

Manages pre-synthesized filler audio responses that are played while
the LLM processes a question. Reduces perceived latency by giving
an immediate acknowledgment before the full answer is ready.

Phase 3 implementation.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.tts import TextToSpeech


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

    Pre-synthesizes filler phrases into audio when ``preload`` is called
    so they can be played instantly when needed, without waiting for TTS.

    Attributes:
        phrases: List of filler phrase strings.
        cache: Pre-synthesized audio bytes keyed by phrase.
    """

    def __init__(self) -> None:
        """Initialize the filler manager.

        Sets up the phrase list and an empty audio cache. Call
        ``preload(tts_engine)`` once a TTS instance is available to
        pre-synthesize audio for all phrases.
        """
        self.phrases = FILLER_PHRASES
        self._cache: dict[str, bytes] = {}

    def get_random_filler(self) -> str:
        """Return a random filler phrase string.

        Useful before TTS is available or when only the text is needed.

        Returns:
            A random filler phrase as a plain string.
        """
        return random.choice(self.phrases)

    def preload(self, tts_engine: TextToSpeech) -> None:
        """Pre-synthesize all filler phrases using the provided TTS engine.

        Args:
            tts_engine: An initialized TextToSpeech instance used to
                convert each phrase into audio bytes.
        """
        for phrase in self.phrases:
            self._cache[phrase] = tts_engine.synthesize(phrase)

    def get_random_filler_audio(self) -> bytes:
        """Return random pre-synthesized filler audio bytes.

        Raises:
            RuntimeError: If ``preload`` has not been called yet.

        Returns:
            Raw audio bytes (PCM format) of a random filler phrase.
        """
        if not self._cache:
            raise RuntimeError(
                "Filler audio not preloaded. Call preload(tts_engine) first."
            )
        phrase = random.choice(self.phrases)
        return self._cache[phrase]
