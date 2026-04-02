"""Query analysis utilities.

Determines whether a question needs live web data to answer.
Used by the bot engine to decide when to invoke SearXNG search.

Phase 3 implementation.
"""

from __future__ import annotations

import re

# Keywords that suggest the question needs live web data.
_WEB_SEARCH_KEYWORDS: tuple[str, ...] = (
    "current",
    "latest",
    "today",
    "price",
    "stock",
    "news",
    "weather",
    "recent",
    "right now",
    "how much does",
    "what time",
)


def needs_web_search(question: str) -> bool:
    """Determine whether a question likely needs live web data.

    Uses keyword heuristics to identify questions about current events,
    real-time prices, weather, news, and other time-sensitive topics
    that cannot be answered from static meeting context alone.

    Args:
        question: The user's question text.

    Returns:
        True if the question likely requires a web search, False otherwise.
    """
    question_lower = question.lower()

    for keyword in _WEB_SEARCH_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
            return True

    return False
