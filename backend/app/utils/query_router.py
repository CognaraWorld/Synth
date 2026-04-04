"""Query analysis and classification utilities.

Determines question categories for smart filler selection and whether
a question needs live web data. Used by the bot engine to select
context-aware filler phrases and decide when to invoke web search.

Phase 3 implementation (expanded for smart fillers).
"""

from __future__ import annotations

from enum import Enum


class QueryCategory(str, Enum):
    """Question categories for routing and filler selection."""

    MEETING_RECAP = "meeting_recap"
    WEB_SEARCH = "web_search"
    TECHNICAL = "technical"
    OPINION = "opinion"
    DOCUMENT = "document"
    GENERAL = "general"


# Questions about the meeting itself — never need web search
_MEETING_ONLY_KEYWORDS: tuple[str, ...] = (
    "what did",
    "who said",
    "summarize",
    "summary",
    "recap",
    "action items",
    "what was discussed",
    "meeting so far",
    "earlier",
    "just said",
    "what happened",
    "catch me up",
    "what were the",
    "key points",
    "takeaways",
)

_TECHNICAL_KEYWORDS: tuple[str, ...] = (
    "how do",
    "how to",
    "implement",
    "code",
    "function",
    "bug",
    "error",
    "api",
    "database",
    "deploy",
    "architecture",
    "algorithm",
    "syntax",
    "debug",
    "refactor",
)

_OPINION_KEYWORDS: tuple[str, ...] = (
    "what do you think",
    "should we",
    "recommend",
    "pros and cons",
    "which is better",
    "opinion",
    "suggest",
    "would you",
    "advice",
)

_DOCUMENT_KEYWORDS: tuple[str, ...] = (
    "from the doc",
    "in the file",
    "uploaded",
    "document says",
    "according to the",
    "the pdf",
    "the report",
    "attachment",
    "the slides",
)


def classify_query(question: str) -> QueryCategory:
    """Classify a question by type using keyword matching.

    Fast (pure string ops, no LLM) — safe for the hot path before
    filler audio is sent. Runs in sub-millisecond time.

    Args:
        question: The user's question text.

    Returns:
        The best-matching QueryCategory.
    """
    q = question.lower()

    for kw in _MEETING_ONLY_KEYWORDS:
        if kw in q:
            return QueryCategory.MEETING_RECAP

    for kw in _DOCUMENT_KEYWORDS:
        if kw in q:
            return QueryCategory.DOCUMENT

    for kw in _TECHNICAL_KEYWORDS:
        if kw in q:
            return QueryCategory.TECHNICAL

    for kw in _OPINION_KEYWORDS:
        if kw in q:
            return QueryCategory.OPINION

    if needs_web_search(question):
        return QueryCategory.WEB_SEARCH

    return QueryCategory.GENERAL


def needs_web_search(question: str) -> bool:
    """Determine whether a question likely needs live web data.

    Default is to SEARCH — only skip for questions clearly about
    the meeting itself (what was said, summaries, etc). This ensures
    the bot always has fresh data for factual questions.

    Args:
        question: The user's question text.

    Returns:
        True if the question likely requires a web search, False otherwise.
    """
    question_lower = question.lower()

    # Skip search for questions clearly about meeting content
    for keyword in _MEETING_ONLY_KEYWORDS:
        if keyword in question_lower:
            return False

    # Search for everything else — prices, facts, coding, general knowledge
    return True
