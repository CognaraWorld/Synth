"""Rolling transcript summarizer.

Maintains a continuously updated summary of the meeting conversation.
As new transcript chunks arrive, the summary is incrementally refined
to capture key points without growing unboundedly. This keeps the
context window manageable for long meetings.

Phase 3 implementation.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class RollingSummary:
    """Incrementally summarizes meeting transcripts.

    Maintains a running summary that is updated each time a new
    transcript chunk is received. Uses the LLM to compress and
    merge new information into the existing summary.

    Thread-safe: all public methods acquire an internal lock for
    shared state. The LLM call itself runs outside the lock to
    avoid blocking other callers.

    Attributes:
        summary: The current accumulated summary text.
        update_interval_chars: Minimum characters before triggering
            a summary update.
    """

    def __init__(self, update_interval_chars: int = 300) -> None:
        """Initialize the rolling summary.

        Args:
            update_interval_chars: Minimum number of new transcript
                characters to accumulate before triggering a summary
                update. Prevents excessive LLM calls for short utterances.
        """
        self.summary: str = ""
        self.update_interval_chars = update_interval_chars
        self._pending_text: str = ""
        self._llm_client: Any | None = None
        self._lock = threading.Lock()

    def set_llm_client(self, llm_client: Any) -> None:
        """Inject the LLM client used for summarization calls.

        Args:
            llm_client: An object with a ``query(context, question)`` method
                (e.g. :class:`~app.core.llm.LLMClient`).
        """
        self._llm_client = llm_client

    async def update(self, new_transcript_chunk: str) -> None:
        """Incorporate a new transcript chunk into the summary.

        Accumulates text until the update interval is reached, then
        calls the LLM to merge new content into the existing summary.
        The LLM call runs outside the lock to avoid blocking.

        Args:
            new_transcript_chunk: New transcript text to incorporate.
        """
        with self._lock:
            self._pending_text += new_transcript_chunk
            if (
                len(self._pending_text) < self.update_interval_chars
                or self._llm_client is None
            ):
                return
            pending = self._pending_text
            current_summary = self.summary

        # LLM call OUTSIDE the lock (it's slow)
        prompt = (
            "You are summarizing a meeting. Here is the current summary:\n"
            f"{current_summary}\n\n"
            "New transcript:\n"
            f"{pending}\n\n"
            "Update the summary to include the key points from the new "
            "transcript. Keep it concise (under 500 words). Focus on "
            "decisions, action items, and important topics discussed."
        )

        try:
            # Support both sync and async LLM clients gracefully.
            result = self._llm_client.query(context="", question=prompt)
            if asyncio.iscoroutine(result):
                result = await result

            if result and result.strip():
                with self._lock:
                    self.summary = result
                    # Only remove the text we actually summarized, preserving
                    # any new text that arrived during the LLM call
                    if self._pending_text.startswith(pending):
                        self._pending_text = self._pending_text[len(pending):]
                    else:
                        self._pending_text = ""
        except Exception as exc:
            logger.warning("Rolling summary update failed: %s", exc)
            # Don't clear _pending_text — retry next time

    def get_summary(self) -> str:
        """Return the current rolling summary.

        If there is pending text that has not yet been summarized, it is
        appended as a note so the caller always sees the freshest content.

        Returns:
            The accumulated summary text, potentially with a pending-text
            addendum. Returns empty string if no transcript has been
            processed yet and no pending text exists.
        """
        with self._lock:
            if self._pending_text:
                return (
                    self.summary
                    + "\n\n[Recent, not yet summarized]: "
                    + self._pending_text
                )
            return self.summary

    def add_pending(self, text: str) -> None:
        """Append text to the pending buffer (thread-safe, synchronous).

        Used by callers that cannot run async update() (e.g., from sync contexts).
        """
        with self._lock:
            self._pending_text += text

    def get_pending_length(self) -> int:
        """Return the character length of text awaiting summarization.

        Returns:
            Number of characters in the pending buffer.
        """
        with self._lock:
            return len(self._pending_text)

    def reset(self) -> None:
        """Clear the summary and all pending text.

        Used when resetting between sessions or when the meeting ends.
        """
        with self._lock:
            self.summary = ""
            self._pending_text = ""
