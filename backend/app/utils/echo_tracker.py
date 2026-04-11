"""Centralized echo tracking for bot output detection.

Prevents the bot from responding to its own transcribed speech by
tracking recent output text per bot. Used by both the webhook handler
(for filtering incoming transcripts) and the bot engine (for recording
what the bot said).
"""

from __future__ import annotations

import threading

_MAX_ENTRIES_PER_BOT = 5

_lock = threading.Lock()
_recent_output: dict[str, list[str]] = {}


def record(bot_id: str, text: str) -> None:
    """Record text the bot just spoke for echo detection."""
    if not bot_id or not text:
        return
    with _lock:
        entries = _recent_output.setdefault(bot_id, [])
        entries.append(text.lower())
        if len(entries) > _MAX_ENTRIES_PER_BOT:
            _recent_output[bot_id] = entries[-_MAX_ENTRIES_PER_BOT:]


def is_echo(bot_id: str, text: str) -> bool:
    """Return True if *text* looks like an echo of recent bot output."""
    if not bot_id or bot_id not in _recent_output:
        return False
    text_lower = text.lower().strip()
    if len(text_lower) <= 10:
        return False
    with _lock:
        for bot_text in _recent_output.get(bot_id, []):
            if text_lower in bot_text or bot_text in text_lower:
                return True
            if len(text_lower.split()) >= 3:
                text_words = set(text_lower.split())
                bot_words = set(bot_text.split())
                overlap = len(text_words & bot_words)
                if overlap / len(text_words) > 0.6:
                    return True
    return False


def cleanup(bot_id: str) -> None:
    """Remove tracking data for a bot that has left."""
    with _lock:
        _recent_output.pop(bot_id, None)
