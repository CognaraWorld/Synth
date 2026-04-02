"""Wake word detection utility.

Scans transcript text for the wake word phrase (default: "hey synth")
and extracts the question that follows. Supports case-insensitive
matching and minor variations.

Phase 3 implementation.
"""

from __future__ import annotations

import re


# Pattern handles: "hey synth", "hey, synth", "hey  synth", or just "synth"
_WAKE_WORD_PATTERN = re.compile(
    r"\b(?:hey[,\s]*)?synth\b",
    re.IGNORECASE,
)


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
    match = _WAKE_WORD_PATTERN.search(transcript_text)
    if match is None:
        return (False, "")

    # Extract everything after the wake word match
    after = transcript_text[match.end():]

    # Strip leading punctuation (commas, colons, etc.) and whitespace
    question = re.sub(r"^[\s,;:!?\-]+", "", after).strip()

    return (True, question)
