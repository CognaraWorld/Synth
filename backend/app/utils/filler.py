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


# Filler phrases are category-specific and length-tuned to cover the
# full ~1.3 s user-perceived pipeline (wake detection + LLM TTFT + TTS
# for the first sentence). Every phrase is 5-9 words; shorter "Sure."
# / "Hmm." style fillers were removed because they leave dead air
# between the filler and the real answer.
_MEETING_RECAP_FILLERS: list[str] = [
    "Let me look back through the meeting.",
    "One second, checking what we discussed earlier.",
    "Let me go through the conversation so far.",
    "Let me pull that from earlier in the call.",
]

_DOCUMENT_FILLERS: list[str] = [
    "Let me check the document for you.",
    "One second, looking through the file.",
    "Let me pull that from the document.",
    "Checking the uploaded file now.",
]

_TECHNICAL_FILLERS: list[str] = [
    "Good question, let me think about that.",
    "Let me work through that one.",
    "Hmm, give me a moment to think.",
    "Let me break that down for you.",
]

_OPINION_FILLERS: list[str] = [
    "Let me think that through for a moment.",
    "Interesting question, give me a second.",
    "Hmm, let me consider that.",
    "Good one, let me think.",
]

_WEB_SEARCH_FILLERS: list[str] = [
    "Let me look that up for you.",
    "One second, let me search that.",
    "Give me a moment to check on that.",
    "Let me pull that up now.",
]

_GENERAL_FILLERS: list[str] = [
    "Let me check on that for you.",
    "One second, let me think about it.",
    "Good question, let me look into that.",
    "Give me a moment to think.",
    "Let me figure that out.",
]

CATEGORY_FILLERS: dict[QueryCategory, list[str]] = {
    QueryCategory.MEETING_RECAP: _MEETING_RECAP_FILLERS,
    QueryCategory.DOCUMENT: _DOCUMENT_FILLERS,
    QueryCategory.TECHNICAL: _TECHNICAL_FILLERS,
    QueryCategory.OPINION: _OPINION_FILLERS,
    QueryCategory.WEB_SEARCH: _WEB_SEARCH_FILLERS,
    QueryCategory.GENERAL: _GENERAL_FILLERS,
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

        Caches by (phrase, voice) so persona voice switches produce
        correct audio instead of reusing the first voice's cache.

        Args:
            tts_engine: An initialized TextToSpeech instance.
        """
        from app.meeting.recall_client import RecallClient
        voice = getattr(tts_engine, "voice", "default")
        for phrase in self._all_phrases():
            cache_key = f"{phrase}:{voice}"
            if cache_key not in self._cache:
                pcm = tts_engine.synthesize(phrase)
                self._cache[cache_key] = pcm
                self._mp3_cache[cache_key] = RecallClient.pcm_to_mp3_b64(pcm)
                # Also keep plain phrase key pointing to latest voice for backward compat
                self._cache[phrase] = pcm
                self._mp3_cache[phrase] = self._mp3_cache[cache_key]

    def get_filler_for_category(self, category: QueryCategory) -> str:
        """Return a random filler phrase for the given category."""
        phrases = CATEGORY_FILLERS.get(category, CATEGORY_FILLERS[QueryCategory.GENERAL])
        return random.choice(phrases)

    def get_personalized_filler(self, category: QueryCategory, speaker: str) -> str:
        """Return a filler phrase personalized with the speaker's name.

        Produces natural acknowledgments like "Sure Yash, let me check."
        so the bot feels conversational and human.
        """
        cleaned_speaker = (speaker or "").strip()
        first_name = cleaned_speaker.split()[0] if cleaned_speaker else ""
        if not first_name:
            return self.get_filler_for_category(category)

        templates = [
            f"Sure {first_name}, let me check.",
            f"Good question {first_name}, one sec.",
            f"On it {first_name}.",
            f"Let me look into that {first_name}.",
            f"Hmm, give me a moment {first_name}.",
        ]
        return random.choice(templates)

    def get_filler_mp3_b64(self, category: QueryCategory, voice: str = "") -> str:
        """Return pre-synthesized base64 MP3 filler for a category.

        Args:
            category: The query category to match fillers against.
            voice: TTS voice name for persona-correct audio lookup.

        Returns:
            Base64-encoded MP3 string, ready to send to Recall.ai.
            Empty string if cache is not loaded.
        """
        if not self._mp3_cache:
            return ""
        phrase = self.get_filler_for_category(category)
        if voice:
            result = self._mp3_cache.get(f"{phrase}:{voice}", "")
            if result:
                return result
        return self._mp3_cache.get(phrase, "")

    def get_filler_audio(self, category: QueryCategory, voice: str = "") -> bytes:
        """Return pre-synthesized PCM filler audio for a category."""
        if not self._cache:
            return b""
        phrase = self.get_filler_for_category(category)
        if voice:
            result = self._cache.get(f"{phrase}:{voice}", b"")
            if result:
                return result
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
