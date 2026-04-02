"""Query complexity router.

Classifies incoming questions by complexity to route them to the
appropriate Claude model tier. Simple factual lookups go to Haiku
for speed; complex analytical questions go to Sonnet for quality.

Phase 3 implementation.
"""

from __future__ import annotations

import re

# Analytical keywords that signal a question requiring deeper reasoning.
_ANALYTICAL_KEYWORDS: tuple[str, ...] = (
    "summarize",
    "analyze",
    "compare",
    "contrast",
    "explain why",
    "implications",
    "impact",
    "pros and cons",
    "trade-offs",
    "evaluate",
    "assess",
    "recommend",
    "strategy",
    "how does this affect",
    "what are the consequences",
)

# Multi-part indicators that suggest the question has several sub-parts.
_MULTI_PART_INDICATORS: tuple[str, ...] = (
    "and also",
    "additionally",
    "furthermore",
    "as well as",
    "on top of that",
)

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


def route(question: str) -> str:
    """Classify a question and determine the target model tier.

    Uses keyword heuristics and structural analysis to determine
    whether a question requires the cheaper/faster Haiku model or
    the more capable Sonnet model.

    Heuristic signals for "sonnet" routing:
        - Multi-part questions (contains "and also", "additionally")
        - Analytical keywords ("analyze", "compare", "implications")
        - Long questions (> 50 words)
        - Questions referencing multiple topics or documents

    Heuristic signals for "haiku" routing:
        - Short factual questions ("what is", "when did")
        - Single-topic lookups
        - Yes/no questions
        - Simple definitions

    Args:
        question: The user's question text.

    Returns:
        "haiku" for simple questions or "sonnet" for complex ones.
    """
    question_lower = question.lower()

    # Check for analytical keywords using word boundaries.
    for keyword in _ANALYTICAL_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
            return "sonnet"

    # Check for multi-part indicators using word boundaries.
    for indicator in _MULTI_PART_INDICATORS:
        if re.search(r'\b' + re.escape(indicator) + r'\b', question_lower):
            return "sonnet"

    # Long questions (> 50 words) are likely complex.
    if len(question.split()) > 50:
        return "sonnet"

    # Multiple question marks suggest a multi-part question.
    if question.count("?") > 1:
        return "sonnet"

    return "haiku"


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
