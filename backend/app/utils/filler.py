"""Context-aware filler response manager.

Manages pre-synthesized filler audio responses that are played while
the LLM processes a question. Selects the most relevant filler based
on the question category (meeting recap, web search, technical, etc.)
to sound more natural and human-like.

Phase 3 implementation (expanded with smart category routing).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from app.utils.query_router import QueryCategory

if TYPE_CHECKING:
    from app.core.tts import TextToSpeech


CATEGORY_FILLERS: dict[QueryCategory, list[str]] = {
    QueryCategory.MEETING_RECAP: [
        "Let me review what was discussed.",
        "One sec, pulling up the conversation.",
        "Sure, let me look back at that.",
        "Give me a moment to check the notes.",
    ],
    QueryCategory.WEB_SEARCH: [
        "Good question, let me look that up.",
        "One moment, checking on that.",
        "Sure, let me find the latest on that.",
        "Let me pull up some info on that.",
    ],
    QueryCategory.TECHNICAL: [
        "Interesting, let me think through that.",
        "Good question, give me a moment.",
        "Let me work through that real quick.",
        "One sec, thinking about that.",
    ],
    QueryCategory.OPINION: [
        "That's a good one, let me think.",
        "Hmm, let me consider that for a second.",
        "Interesting question, one moment.",
        "Let me think about the best approach.",
    ],
    QueryCategory.DOCUMENT: [
        "Let me check the documents.",
        "One sec, looking through the files.",
        "Sure, let me reference that.",
        "Give me a moment to pull that up.",
    ],
    QueryCategory.GENERAL: [
        "Sure, one moment.",
        "Let me look into that.",
        "Good question, give me a sec.",
        "Hmm, one sec.",
        "Let me check on that.",
    ],
}


class FillerManager:
    """Manages context-aware filler audio for latency masking.

    Pre-synthesizes filler phrases for all categories into audio at
    startup so they can be played instantly when needed.

    Attributes:
        _cache: Pre-synthesized PCM audio keyed by phrase.
        _mp3_cache: Pre-converted base64 MP3 keyed by phrase.
    """

    def __init__(self) -> None:
        self._cache: dict[str, bytes] = {}
        self._mp3_cache: dict[str, str] = {}

    def _all_phrases(self) -> list[str]:
        """Return all filler phrases across all categories."""
        phrases: list[str] = []
        for cat_phrases in CATEGORY_FILLERS.values():
            phrases.extend(cat_phrases)
        return phrases

    def preload(self, tts_engine: TextToSpeech) -> None:
        """Pre-synthesize all filler phrases across all categories.

        Args:
            tts_engine: An initialized TextToSpeech instance.
        """
        from app.meeting.recall_client import RecallClient
        for phrase in self._all_phrases():
            if phrase not in self._cache:
                pcm = tts_engine.synthesize(phrase)
                self._cache[phrase] = pcm
                self._mp3_cache[phrase] = RecallClient.pcm_to_mp3_b64(pcm)

    def get_filler_for_category(self, category: QueryCategory) -> str:
        """Return a random filler phrase for the given category."""
        phrases = CATEGORY_FILLERS.get(category, CATEGORY_FILLERS[QueryCategory.GENERAL])
        return random.choice(phrases)

    def get_filler_mp3_b64(self, category: QueryCategory) -> str:
        """Return pre-synthesized base64 MP3 filler for a category.

        Args:
            category: The query category to match fillers against.

        Returns:
            Base64-encoded MP3 string, ready to send to Recall.ai.
            Empty string if cache is not loaded.
        """
        if not self._mp3_cache:
            return ""
        phrase = self.get_filler_for_category(category)
        return self._mp3_cache.get(phrase, "")

    def get_filler_audio(self, category: QueryCategory) -> bytes:
        """Return pre-synthesized PCM filler audio for a category."""
        if not self._cache:
            return b""
        phrase = self.get_filler_for_category(category)
        return self._cache.get(phrase, b"")

    # Backward-compatible methods
    def get_random_filler(self) -> str:
        """Return a random filler phrase (general category)."""
        return self.get_filler_for_category(QueryCategory.GENERAL)

    def get_random_filler_mp3_b64(self) -> str:
        """Return random pre-synthesized filler as base64 MP3."""
        return self.get_filler_mp3_b64(QueryCategory.GENERAL)

    def get_random_filler_audio(self) -> bytes:
        """Return random pre-synthesized filler audio bytes (PCM)."""
        return self.get_filler_audio(QueryCategory.GENERAL)
