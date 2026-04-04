"""Passive insight detector.

Scans meeting transcripts for verifiable factual claims (numbers,
statistics, technical data). When a claim is detected, verifies it
via web search and stores a correction if the claim is wrong.

Runs in the background without interrupting the meeting.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Patterns that suggest a verifiable factual claim
_CLAIM_PATTERNS = [
    # Numbers with units: "200 billion", "50 percent", "$3.5 million"
    re.compile(r'\b\d[\d,.]*\s*(?:billion|million|trillion|thousand|percent|%|dollars?|rupees?|euros?)\b', re.IGNORECASE),
    # Market/finance: "market cap is", "trading at", "worth about"
    re.compile(r'\b(?:market\s*cap|trading\s*at|worth\s*(?:about|around)?|valued\s*at|revenue\s*(?:is|was|of))\b', re.IGNORECASE),
    # Technical specs: "runs at 3.5 GHz", "has 16 cores"
    re.compile(r'\b\d+\s*(?:GHz|MHz|GB|TB|MB|KB|cores?|threads?|nm|watts?)\b', re.IGNORECASE),
    # Definitive claims: "X was founded in", "X has Y employees"
    re.compile(r'\b(?:founded\s*in|launched\s*in|has\s*\d+\s*employees|population\s*(?:is|of))\b', re.IGNORECASE),
    # Dates with claims: "released in 2024", "since 2019"
    re.compile(r'\b(?:released|launched|started|founded|invented)\s*(?:in|on)\s*\d{4}\b', re.IGNORECASE),
]


def contains_verifiable_claim(text: str) -> bool:
    """Check if text contains a factual claim worth verifying.

    Args:
        text: Transcript text to scan.

    Returns:
        True if the text contains numbers, stats, or definitive claims.
    """
    for pattern in _CLAIM_PATTERNS:
        if pattern.search(text):
            return True
    return False


async def verify_claim(
    text: str,
    speaker: str,
    search_client: Any,
    llm_client: Any,
) -> dict[str, str] | None:
    """Verify a factual claim via web search + LLM analysis.

    Args:
        text: The transcript text containing the claim.
        speaker: Who said it.
        search_client: SearchClient for web search.
        llm_client: LLMClient for analysis.

    Returns:
        Dict with 'claim', 'correction', 'speaker' if error found.
        None if the claim is correct or unverifiable.
    """
    try:
        # Search for the factual claim
        search_results = await search_client.search_formatted(text)

        if not search_results or "No results found" in search_results:
            return None

        # Ask LLM to compare the claim against search results
        prompt = (
            "A meeting participant said the following:\n"
            f'"{text}"\n\n'
            "Here are current web search results:\n"
            f"{search_results}\n\n"
            "Is there a factual error in what the participant said? "
            "Focus ONLY on verifiable facts — numbers, dates, statistics, prices. "
            "Ignore opinions, estimates, or approximate language like 'about' or 'around'.\n\n"
            "If there IS a clear factual error, respond with EXACTLY this format:\n"
            "ERROR: [what they said wrong] -> [what it actually is]\n\n"
            "If the statement is correct, approximately correct, or unverifiable, "
            "respond with EXACTLY:\n"
            "CORRECT"
        )

        result = await llm_client.async_query(
            context="",
            question=prompt,
            system_prompt="You are a fact-checker. Be precise. Only flag clear errors, not approximations.",
        )

        result = result.strip()

        if result.startswith("ERROR:"):
            correction = result[6:].strip()
            logger.warning(
                "INSIGHT DETECTED: %s said '%s' — %s",
                speaker, text[:60], correction,
            )
            return {
                "speaker": speaker,
                "claim": text,
                "correction": correction,
            }

        return None

    except Exception as exc:
        logger.debug("Insight verification failed: %s", exc)
        return None
