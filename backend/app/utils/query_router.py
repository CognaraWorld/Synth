"""Query complexity router.

Classifies incoming questions by complexity to route them to the
appropriate Claude model tier. Simple factual lookups go to Haiku
for speed; complex analytical questions go to Sonnet for quality.

Phase 3 implementation.
"""

from __future__ import annotations


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
    # TODO: Implement keyword-based heuristics for complexity classification
    # TODO: Consider question length, structure, and analytical keywords
    raise NotImplementedError("Phase 3 implementation")
