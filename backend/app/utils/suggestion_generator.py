"""Generate contextual chat prompt suggestions."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_DEFAULT_SUGGESTIONS = [
    "What were the key decisions?",
    "Summarize the action items",
    "What topics were discussed?",
    "Who said what about the timeline?",
]

_cache: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 600
_CACHE_MAX_SIZE = 500


async def generate_suggestions(
    summary_content: str | None,
    transcript_tail: str | None,
    llm_query_fn,
) -> list[str]:
    """Generate 3-4 contextual prompt suggestions."""
    source = summary_content or transcript_tail
    if not source:
        return _DEFAULT_SUGGESTIONS[:4]

    try:
        result = await llm_query_fn(
            context=source[:2000],
            question=(
                "Based on this meeting content, suggest exactly 4 questions a user might want to ask. "
                "Return ONLY a JSON array of strings, nothing else. Example: "
                '["Question 1?", "Question 2?", "Question 3?", "Question 4?"]'
            ),
            system_prompt="You generate concise, relevant meeting questions. Return only valid JSON.",
        )
        parsed = json.loads(result.strip())
        if isinstance(parsed, list) and len(parsed) >= 2:
            return [str(suggestion).strip() for suggestion in parsed[:4] if str(suggestion).strip()]
    except Exception:
        logger.warning("Failed to generate suggestions, using defaults", exc_info=True)

    return _DEFAULT_SUGGESTIONS[:4]


def get_cached_suggestions(meeting_id: str) -> list[str] | None:
    """Return cached suggestions if not expired."""
    import time

    entry = _cache.get(meeting_id)
    if entry and entry["expires"] > time.time():
        return entry["suggestions"]
    return None


def cache_suggestions(meeting_id: str, suggestions: list[str]) -> None:
    """Store suggestions in cache with bounded size."""
    import time

    # Evict expired entries when cache is full
    if len(_cache) >= _CACHE_MAX_SIZE:
        now = time.time()
        expired = [k for k, v in _cache.items() if v["expires"] <= now]
        for k in expired:
            del _cache[k]
        # If still full after expiry eviction, remove oldest entries
        if len(_cache) >= _CACHE_MAX_SIZE:
            oldest = sorted(_cache, key=lambda k: _cache[k]["expires"])
            for k in oldest[: len(_cache) - _CACHE_MAX_SIZE + 1]:
                del _cache[k]

    _cache[meeting_id] = {
        "suggestions": suggestions,
        "expires": time.time() + _CACHE_TTL_SECONDS,
    }
