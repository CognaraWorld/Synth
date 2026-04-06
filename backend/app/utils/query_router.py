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


# Questions about the meeting itself — never need web search.
# These are matched as substrings (case-insensitive). Be conservative when
# adding new patterns: substrings like "what was" would falsely match
# "what was the capital of France", so only add patterns where a meeting
# reference is unambiguous.
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
    "we discussed",
    "we talked about",
    "we just",
    "i said",
    "you said",
    "he said",
    "she said",
    "they said",
    "during this meeting",
    "during this call",
    "in this meeting",
    "in this call",
    "from this meeting",
    "from our meeting",
    "what was decided",
    "what we decided",
    "the team decided",
    "minutes ago",
    "from earlier",
    "earlier in",
    "recap the",
    "summarize the",
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
    "the document",
    "in the doc",
    "in the pdf",
    "in the report",
    "in the slides",
    "in the spreadsheet",
    "the spreadsheet",
    "the file says",
    "the doc says",
    "the report says",
    "the slides show",
    "the slides say",
    "from the file",
    "from the pdf",
    "from the report",
    "from the slides",
    "i uploaded",
    "you uploaded",
)

# Strict keyword YES list used by classify_query() to label questions for
# filler-phrase routing. Distinct from needs_web_search() below, which has
# more permissive default-yes semantics for the actual gate decision.
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


def classify_query(question: str) -> QueryCategory:
    """Classify a question by type using keyword matching.

    Fast (pure string ops, no LLM) — safe for the hot path before
    filler audio is sent. Runs in sub-millisecond time.

    Note: this function uses the strict ``_WEB_SEARCH_KEYWORDS`` YES list
    for the WEB_SEARCH category — keeping ``GENERAL`` meaningful for chat-
    style questions and the matching filler picks. The actual web-search
    gate uses :func:`needs_web_search` which has more permissive
    default-yes semantics. The two functions intentionally diverge.

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

    # Strict keyword check for the WEB_SEARCH filler category — distinct
    # from needs_web_search() below which is the actual gate.
    for kw in _WEB_SEARCH_KEYWORDS:
        if kw in q:
            return QueryCategory.WEB_SEARCH

    return QueryCategory.GENERAL


def needs_web_search(question: str) -> bool:
    """Determine whether a question should trigger a web search.

    Default behavior is to **return True** (search). Returns False only
    when the question clearly belongs to meeting context or document
    context — i.e., when we are confident the answer lives in the
    transcript or in an uploaded file.

    This prioritizes recall (don't miss searches) over precision (don't
    search unnecessarily). The cost of an unneeded Serper call is small
    (~200-500ms + ~$0.001); the cost of a missing web answer is a wrong
    or incomplete response to the user.

    Args:
        question: The user's question text.

    Returns:
        True if the question should be sent to web search,
        False if the question is clearly meeting-only or document-only.
    """
    question_lower = question.lower()

    # Skip search for questions clearly about the current/past meetings
    for keyword in _MEETING_ONLY_KEYWORDS:
        if keyword in question_lower:
            return False

    # Skip search for questions clearly about uploaded documents
    for keyword in _DOCUMENT_KEYWORDS:
        if keyword in question_lower:
            return False

    # Default: search. Better to have extra context than to miss a needed lookup.
    return True
