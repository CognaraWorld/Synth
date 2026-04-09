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


_WEB_SEARCH_KEYWORDS: tuple[str, ...] = (
    "price",
    "cost",
    "weather",
    "news",
    "latest",
    "current",
    "today",
    "stock",
    "market",
    "crypto",
    "bitcoin",
    "search",
    "google",
    "look up",
    "find out",
    "what is the",
    "who is",
    "when did",
    "where is",
    "how much",
    "how many",
    "statistics",
    "data on",
    "trending",
    "update on",
    "recent",
    "score",
    "result",
    "rate",
    "convert",
    "exchange",
    "definition",
    "meaning of",
    "capital of",
    "population",
)


def needs_web_search(question: str) -> bool:
    """Determine whether a question likely needs live web data.

    Only searches when the question contains keywords indicating
    external data is needed (prices, news, facts, lookups).
    Skips search for meeting content, opinions, and general chat.

    Args:
        question: The user's question text.

    Returns:
        True if the question likely requires a web search, False otherwise.
    """
    question_lower = question.lower()

    # Never search for meeting content questions
    for keyword in _MEETING_ONLY_KEYWORDS:
        if keyword in question_lower:
            return False

    # Only search when question explicitly needs external data
    for keyword in _WEB_SEARCH_KEYWORDS:
        if keyword in question_lower:
            return True

    return False


def classify_chat_complexity(question: str) -> str:
    """Classify a chat question as simple or complex."""
    question_lower = question.lower().strip()
    word_count = len(question_lower.split())

    if question.count("?") >= 2:
        return "complex"
    if word_count > 40:
        return "complex"

    comparison_words = {
        "compare",
        "contrast",
        "vs",
        "versus",
        "difference",
        "differences",
        "better",
        "worse",
        "pros and cons",
        "trade-off",
        "tradeoff",
    }
    if any(word in question_lower for word in comparison_words):
        return "complex"

    analytical_words = {
        "analyze",
        "analyse",
        "explain why",
        "explain how",
        "step by step",
        "break down",
        "walk me through",
        "deep dive",
        "implications",
        "root cause",
    }
    if any(word in question_lower for word in analytical_words):
        return "complex"

    synthesis_words = {
        "summarize everything",
        "overall assessment",
        "big picture",
        "what should we",
        "recommend",
        "strategy",
    }
    if any(word in question_lower for word in synthesis_words):
        return "complex"

    return "simple"
