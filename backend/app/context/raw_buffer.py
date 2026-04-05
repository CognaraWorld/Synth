"""Structured transcript buffer.

Maintains a sliding window of recent transcript with speaker attribution,
timestamps, and turn-type classification. Provides formatted output
for the LLM with conversational context (who said what, when, and
whether it was a question, decision, or action item).

Phase 9 implementation (replaces plain-text Phase 3 buffer).
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

# Words that look like speaker prefixes but are actually labels/headings
_NON_SPEAKER_PREFIXES = frozenset({
    "note", "example", "update", "action", "decision", "question",
    "summary", "context", "background", "result", "output", "input",
    "warning", "error", "info", "status", "reply", "response",
})


def _detect_type(text: str) -> str:
    """Classify a transcript turn by its conversational role.

    Fast keyword scan — no LLM, sub-millisecond.
    """
    t = text.lower().strip()
    # Question: ? at end of text, or starts with a question word
    if t.rstrip().endswith("?") or re.match(
        r"^(who|what|where|when|why|how|is|are|was|were|do|does|did|can|could|should|would|will)\b", t
    ):
        return "question"
    if any(w in t for w in ("let's go with", "agreed", "decided", "final", "decision is", "we'll do")):
        return "decision"
    if any(w in t for w in ("i'll", "action item", "will do", "take care of", "i will", "let me handle")):
        return "action_item"
    return "statement"


class RawTranscriptBuffer:
    """Structured sliding-window buffer for recent meeting transcript.

    Stores transcript entries as structured dicts with speaker, timestamp,
    and turn-type classification. Groups consecutive turns from the same
    speaker. Formats output with time-ago labels and type tags for the LLM.

    Thread-safe: all public methods acquire an internal lock.

    Attributes:
        max_minutes: Maximum age in minutes for retained entries.
    """

    def __init__(self, max_minutes: int = 10) -> None:
        self.max_minutes = max_minutes
        self._entries: deque[dict[str, Any]] = deque(maxlen=400)
        self._lock = threading.Lock()

    def _prune(self) -> list[tuple[datetime, str]]:
        """Remove entries older than max_minutes and return them.

        Returns pruned entries as (timestamp, text) tuples for backward
        compatibility with the embed buffer in ContextManager.

        Must be called while holding ``self._lock``.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.max_minutes)
        pruned: list[tuple[datetime, str]] = []
        while self._entries and self._entries[0]["timestamp"] < cutoff:
            entry = self._entries.popleft()
            pruned.append((entry["timestamp"], f"{entry['speaker']}: {entry['text']}"))
        return pruned

    def append(
        self,
        text: str,
        timestamp: datetime | None = None,
        speaker: str = "",
    ) -> list[tuple[datetime, str]]:
        """Add a new transcript entry to the buffer.

        If the text contains a "Speaker: text" format (legacy callers),
        the speaker is extracted automatically. Only treats the prefix as
        a speaker name if it looks like a real name (1-3 capitalized words,
        not a common label like "Note" or "Example").

        Args:
            text: The transcript text to store.
            timestamp: When captured. Defaults to now (UTC).
            speaker: Name of the speaker.

        Returns:
            List of (timestamp, text) tuples that were evicted (by deque
            overflow or time-based pruning). Caller should route these
            to the embed buffer so they are not permanently lost.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Extract speaker from "Speaker: text" format if not provided.
        # Tighten heuristic: only treat prefix as speaker when it looks
        # like a name (1-3 capitalized words, not a common label).
        if not speaker and ": " in text:
            parts = text.split(": ", 1)
            candidate = parts[0].strip()
            words = candidate.split()
            if (
                1 <= len(words) <= 3
                and all(w[0].isupper() for w in words if w)
                and candidate.lower() not in _NON_SPEAKER_PREFIXES
            ):
                speaker = candidate
                text = parts[1]

        turn_type = _detect_type(text)

        evicted: list[tuple[datetime, str]] = []

        with self._lock:
            # Group consecutive turns from same speaker
            if self._entries and self._entries[-1]["speaker"] == speaker and speaker:
                last = self._entries[-1]
                last["text"] += " " + text
                last["timestamp"] = timestamp
                # Upgrade type if new text changes it
                new_type = _detect_type(last["text"])
                if new_type != "statement":
                    last["type"] = new_type
            else:
                # Capture entry about to be silently evicted by deque maxlen
                if len(self._entries) == self._entries.maxlen:
                    old = self._entries[0]
                    evicted.append((old["timestamp"], f"{old['speaker']}: {old['text']}"))

                self._entries.append({
                    "speaker": speaker or "Unknown",
                    "text": text,
                    "timestamp": timestamp,
                    "type": turn_type,
                })

            # Time-based pruning
            pruned = self._prune()
            evicted.extend(pruned)

        return evicted

    def get_recent(self, minutes: int = 5) -> str:
        """Retrieve formatted recent transcript for LLM context.

        Formats each turn with time-ago label, speaker name, and type
        tag for decisions/questions/action items.

        Args:
            minutes: Number of minutes of history to retrieve.

        Returns:
            Formatted transcript string ready for LLM context.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        now = time.time()

        with self._lock:
            recent = [e for e in self._entries if e["timestamp"] >= cutoff]

        if not recent:
            return ""

        lines: list[str] = []
        for entry in recent:
            ago = int((now - entry["timestamp"].timestamp()) / 60)
            ago_label = f"[{ago}m ago]" if ago > 0 else "[just now]"

            prefix = ""
            if entry["type"] == "decision":
                prefix = "[DECISION] "
            elif entry["type"] == "question":
                prefix = "[QUESTION] "
            elif entry["type"] == "action_item":
                prefix = "[ACTION] "

            lines.append(f"{ago_label} {entry['speaker']}: {prefix}{entry['text']}")

        return "\n".join(lines)

    def get_full_text(self) -> str:
        """Return all buffered text as plain chronological transcript."""
        with self._lock:
            return "\n".join(
                f"{e['speaker']}: {e['text']}" for e in self._entries
            )

    def get_entries(self) -> list[dict[str, Any]]:
        """Return a copy of all structured entries."""
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        """Clear all entries from the buffer."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        """Return the number of entries currently in the buffer."""
        with self._lock:
            return len(self._entries)
