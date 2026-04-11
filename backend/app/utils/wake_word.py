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
    punctuation between words. Includes common phonetic misheard
    variants from meeting caption STT systems.

    Args:
        wake_word: The trigger phrase (e.g. "hey synth").

    Returns:
        Compiled regex pattern.
    """
    parts = wake_word.strip().lower().split()
    if len(parts) == 2 and parts[0] == "hey" and parts[1] == "synth":
        # "hey synth" — include phonetic variants that caption STT produces.
        # Prefix is REQUIRED to avoid false positives on bare words like
        # "since", "said", "system" in normal speech.
        prefix = r"(?:hey|he|hay|a|they|hi|both|but)[,.\s]+"
        name = (
            r"(?:synth|sint|sent|since|sink|sync|sins|sinth|cinth|"
            r"synths|sense|said|sit|assist|assistant|listen|"
            r"tasted|system|cyst|sixth|sis|says)"
        )
        return re.compile(
            rf"\b{prefix}{name}\b",
            re.IGNORECASE,
        )
    if len(parts) == 2 and parts[0] == "hey" and parts[1] == "assistant":
        # "hey assistant" — include phonetic variants that meeting STT
        # commonly produces. Prefix is REQUIRED to prevent false positives
        # on bare "assistant" or "assist" in normal speech.
        prefix = r"(?:hey|he|hay|a|as|they|hi|both|but)[,.\s]+"
        name = (
            r"(?:assistant|assistance|assisted|assistent|"
            r"a\s*sistant|a\s*system|a\s*distance|"
            r"assists?|assess|assessing|assisting|"
            r"assist\s*ten|assist\s*and|assist\s*in|"
            r"insisted|instant|persistent)"
        )
        return re.compile(
            rf"\b{prefix}{name}\b",
            re.IGNORECASE,
        )
    if (len(parts) == 1 and parts[0] == "nova") or (len(parts) == 2 and parts[0] == "hey" and parts[1] == "nova"):
        # "nova" or "hey nova" — accepts both with phonetic variants.
        prefix = r"(?:(?:hey|he|hay|hi|they|okay)[,.\s]+)?"  # optional prefix
        name = r"(?:nova|no\s*va|nora|noah|mova)"
        return re.compile(
            rf"\b{prefix}{name}\b",
            re.IGNORECASE,
        )
    if len(parts) == 2 and parts[0] == "hey":
        name = re.escape(parts[1])
        return re.compile(
            rf"\b(?:hey[,\s]*)?{name}\b",
            re.IGNORECASE,
        )
    # Single word or custom phrase — exact match with word boundaries
    escaped = re.escape(wake_word.strip())
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


_DIRECTED_AT_OTHER_PATTERN = re.compile(
    r"^(?:hey\s+)?(\w+)[,\s]+(?:what\s+do\s+you\s+think|can\s+you|could\s+you|"
    r"would\s+you|do\s+you|your\s+(?:thoughts|opinion|take)|"
    r"what(?:'s|\s+is)\s+your|tell\s+(?:us|me)|you\s+(?:want|think|agree))",
    re.IGNORECASE,
)

_GENERIC_ADDRESSEES = frozenset({
    "everyone", "guys", "team", "folks", "all", "people", "somebody", "someone",
})


def is_directed_at_other(
    text: str,
    bot_names: tuple[str, ...] = (),
    known_participants: frozenset[str] = frozenset(),
) -> bool:
    """Return True when the utterance is clearly addressed to another person.

    Detects patterns like "John, what do you think?" or "Sarah, can you
    explain?" and returns True so the bot stays silent. Returns False
    (i.e. "might be for me") when:
    - The addressee is the bot's own name
    - The addressee is a generic group word ("everyone", "team")
    - No directed-at pattern is found
    """
    match = _DIRECTED_AT_OTHER_PATTERN.match(text.strip())
    if not match:
        return False

    addressee = match.group(1).lower()

    if addressee in _GENERIC_ADDRESSEES:
        return False

    for bot_name in bot_names:
        if addressee == bot_name.lower() or addressee == bot_name.split()[0].lower():
            return False

    # If we know the meeting participants and the addressee matches one, it's
    # directed at them, not the bot.
    if known_participants:
        for participant in known_participants:
            if addressee == participant.lower() or addressee == participant.split()[0].lower():
                return True

    # Addressee is a proper name (capitalized in original text) — likely a person
    original_word = text.strip().split(",")[0].split()[-1] if "," in text else ""
    if original_word and original_word[0].isupper():
        return True

    return False


def detect(
    transcript_text: str,
    wake_word: str = "nova",
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
    # Fast path: exact case-insensitive match with word boundary check
    ww_lower = wake_word.strip().lower()
    text_lower = transcript_text.lower()
    exact_pos = text_lower.find(ww_lower)
    if exact_pos != -1:
        # Verify word boundaries on both sides to prevent
        # "supernova" or "innova" from matching bare "nova"
        end_pos = exact_pos + len(ww_lower)
        leading_ok = exact_pos == 0 or not text_lower[exact_pos - 1].isalnum()
        trailing_ok = end_pos >= len(text_lower) or not text_lower[end_pos].isalnum()
        if leading_ok and trailing_ok:
            after = transcript_text[end_pos:]
            question = re.sub(r"^[\s,;:!?.\-]+", "", after).strip()
            return (True, question)

    # Fuzzy path: phonetic variants for STT mishearings
    pattern = _build_pattern(wake_word)
    match = pattern.search(transcript_text)
    if match is None:
        return (False, "")

    # Extract everything after the wake word match
    after = transcript_text[match.end():]

    # Strip leading punctuation and STT artifact words (e.g. "ten" from "assist ten")
    question = re.sub(r"^[\s,;:!?.\-]+", "", after).strip()
    question = re.sub(r"^(?:ten|and|in|the)\b[\s,;:!?.\-]*", "", question, flags=re.IGNORECASE).strip()

    return (True, question)
