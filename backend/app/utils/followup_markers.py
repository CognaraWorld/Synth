"""Helpers for deciding whether a short follow-up is coherent enough to route."""

from __future__ import annotations

import re

_COHERENCE_WORD_MARKERS = frozenset({
    "what", "who", "where", "when", "why", "how",
    "can", "could", "would", "should", "will", "do", "does", "did",
    "is", "are", "was", "were", "have", "has",
    "tell", "explain", "show", "give", "find", "search",
    "yes", "no", "yeah", "okay", "sure",
    "thank", "stop", "enough",
    "about", "think", "know", "remember", "mean",
    "also", "and", "but", "more",
})
_COHERENCE_PHRASE_PATTERNS = (
    re.compile(r"\bwhat about\b"),
)
_COHERENCE_WORD_PATTERN = re.compile(r"\b[\w']+\b")


def has_coherence_marker(text: str) -> bool:
    """Return True when *text* contains a follow-up cue on word boundaries."""
    text_lower = text.lower().strip()
    if not text_lower:
        return False
    if "?" in text_lower:
        return True
    if any(pattern.search(text_lower) for pattern in _COHERENCE_PHRASE_PATTERNS):
        return True
    words = set(_COHERENCE_WORD_PATTERN.findall(text_lower))
    return bool(words & _COHERENCE_WORD_MARKERS)
