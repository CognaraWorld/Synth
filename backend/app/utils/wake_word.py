"""Wake word detection utility.

Scans transcript text for the wake word phrase (default: "hey synth")
and extracts the question that follows. Supports case-insensitive
matching and minor variations.

Phase 3 implementation.
"""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=16)
def _build_pattern(wake_word: str) -> re.Pattern:
    """Build a regex pattern for the given wake word.

    Supports "hey <name>" and bare "<name>" patterns with optional
    punctuation between words. Cached for performance.

    Args:
        wake_word: The trigger phrase (e.g. "hey synth").

    Returns:
        Compiled regex pattern.
    """
    parts = wake_word.strip().lower().split()
    if len(parts) == 2 and parts[0] == "hey":
        # "hey synth" → matches "hey synth", "hey, synth", or just "synth"
        name = re.escape(parts[1])
        return re.compile(
            rf"\b(?:hey[,\s]*)?{name}\b",
            re.IGNORECASE,
        )
    # Single word or custom phrase — exact match with word boundaries
    escaped = re.escape(wake_word.strip())
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def detect(
    transcript_text: str,
    wake_word: str = "hey synth",
) -> tuple[bool, str]:
    """Detect the wake word in transcript text and extract the question.

    Scans the provided transcript text for the wake word. If found,
    extracts everything after the wake word as the user's question.

    Args:
        transcript_text: Raw transcript text to scan for the wake word.
        wake_word: The trigger phrase to listen for (case-insensitive).

    Returns:
        A tuple of (detected, extracted_question) where:
            - detected: True if the wake word was found.
            - extracted_question: The text following the wake word,
              stripped of leading/trailing whitespace. Empty string
              if wake word was not detected.

    Examples:
        >>> detect("Hey Synth, what was the Q3 revenue?")
        (True, "what was the Q3 revenue?")
        >>> detect("Let's discuss the budget next.")
        (False, "")
    """
    pattern = _build_pattern(wake_word)
    match = pattern.search(transcript_text)
    if match is None:
        return (False, "")

    # Extract everything after the wake word match
    after = transcript_text[match.end():]

    # Strip leading punctuation (commas, colons, etc.) and whitespace
    question = re.sub(r"^[\s,;:!?\-]+", "", after).strip()

    return (True, question)
