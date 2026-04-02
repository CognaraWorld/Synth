"""Raw transcript buffer.

Maintains a sliding window of recent raw transcript text with timestamps.
Provides quick access to the last N minutes of conversation for inclusion
in the LLM context window alongside the rolling summary.

Phase 3 implementation.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta


class RawTranscriptBuffer:
    """Fixed-window buffer for recent raw transcript segments.

    Stores timestamped transcript entries and provides efficient
    retrieval of the most recent conversation window. Automatically
    prunes entries older than max_minutes.

    Thread-safe: all public methods acquire an internal lock.

    Attributes:
        max_minutes: Maximum number of minutes of transcript to retain.
    """

    def __init__(self, max_minutes: int = 10) -> None:
        """Initialize the transcript buffer.

        Args:
            max_minutes: Maximum age in minutes for retained entries.
                Entries older than this are pruned on access.
        """
        self.max_minutes = max_minutes
        self._entries: list[tuple[datetime, str]] = []
        self._lock = threading.Lock()

    def _prune(self) -> None:
        """Remove entries older than max_minutes.

        Must be called while holding ``self._lock``.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=self.max_minutes)
        self._entries = [
            (ts, text) for ts, text in self._entries if ts >= cutoff
        ]

    def append(self, text: str, timestamp: datetime | None = None) -> None:
        """Add a new transcript entry to the buffer.

        Args:
            text: The transcript text to store.
            timestamp: When this text was captured. Defaults to now.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        with self._lock:
            self._entries.append((timestamp, text))
            self._prune()

    def get_recent(self, minutes: int = 5) -> str:
        """Retrieve the most recent transcript text.

        Args:
            minutes: Number of minutes of history to retrieve.
                Must be <= max_minutes.

        Returns:
            Concatenated transcript text from the requested time window,
            ordered chronologically.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        with self._lock:
            filtered = [
                text for ts, text in self._entries if ts >= cutoff
            ]

        return "\n".join(filtered)

    def get_full_text(self) -> str:
        """Return all buffered text concatenated chronologically.

        Returns:
            Concatenated transcript text from all entries currently in
            the buffer, joined by newlines.
        """
        with self._lock:
            return "\n".join(text for _ts, text in self._entries)

    def clear(self) -> None:
        """Clear all entries from the buffer.

        Used when resetting between sessions or when the meeting ends.
        """
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        """Return the number of entries currently in the buffer."""
        with self._lock:
            return len(self._entries)
