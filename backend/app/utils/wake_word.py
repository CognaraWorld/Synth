"""Wake word detection utility.

Scans transcript text for the wake word phrase (default: "hey synth")
and extracts the question that follows. Supports case-insensitive
matching and minor variations.

Phase 3 implementation.
"""

from __future__ import annotations


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
    # TODO: Case-insensitive wake word matching
    # TODO: Handle variations (e.g., "hey synth," vs "hey synth")
    # TODO: Extract and clean the question text after the wake word
    raise NotImplementedError("Phase 3 implementation")
