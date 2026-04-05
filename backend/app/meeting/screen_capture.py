"""Screen content capture, change detection, and content extraction.

Receives screenshots from Recall.ai, detects meaningful screen changes
(vs. video content or identical frames), extracts content via Gemini Vision,
and stores results in the meeting ContextManager.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.context.manager import ContextManager
    from app.core.gemini import GeminiVisionClient

logger = logging.getLogger(__name__)

# Video detection: if this many distinct frames arrive within the window -> video
_VIDEO_CHANGE_COUNT = 4
_VIDEO_WINDOW_SECONDS = 5.0

class CaptureOutcome(str, Enum):
    SKIPPED = "skipped"        # duplicate frame (consecutive or previously seen)
    VIDEO = "video"            # rapid changes detected -- video playing
    EXTRACTED = "extracted"    # content successfully extracted
    EMPTY = "empty"            # Gemini returned no useful content


@dataclass
class CaptureResult:
    outcome: CaptureOutcome
    content: str = ""
    # Human-readable apology to speak aloud (only set on first VIDEO detection)
    apology: str = ""


class ScreenCaptureManager:
    """Manages per-session screen capture, change detection, and extraction.

    Attributes:
        session_id: The meeting session this manager belongs to.
        context_manager: Where extracted screen content is stored.
        gemini: Gemini Vision client for content extraction (None = disabled).
    """

    def __init__(
        self,
        session_id: str,
        context_manager: "ContextManager",
        gemini: "GeminiVisionClient | None" = None,
    ) -> None:
        self.session_id = session_id
        self.context_manager = context_manager
        self.gemini = gemini

        self._lock = asyncio.Lock()
        self._last_hash: str | None = None
        self._seen_hashes: set[str] = set()
        # Monotonic timestamps of frames that had a different hash from previous
        self._change_times: deque[float] = deque(maxlen=20)
        # Track whether we've already sent the video-apology this session
        self._video_warned: bool = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hash_image(self, image_bytes: bytes) -> str:
        return hashlib.md5(image_bytes).hexdigest()

    def _prune_change_times(self) -> None:
        """Remove timestamps outside the detection window."""
        cutoff = time.monotonic() - _VIDEO_WINDOW_SECONDS
        while self._change_times and self._change_times[0] < cutoff:
            self._change_times.popleft()

    def _is_video(self) -> bool:
        self._prune_change_times()
        return len(self._change_times) >= _VIDEO_CHANGE_COUNT

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def handle_screenshot(self, image_bytes: bytes) -> CaptureResult:
        """Process a screenshot received from the meeting.

        Change detection, deduplication, and video detection are performed
        under the lock. The slow Gemini extraction runs outside the lock so
        that subsequent frames are not blocked while awaiting the API call.

        Args:
            image_bytes: Raw PNG/JPEG screenshot bytes.

        Returns:
            CaptureResult with the outcome and any extracted content.
        """
        if not image_bytes:
            return CaptureResult(outcome=CaptureOutcome.SKIPPED)

        async with self._lock:
            new_hash = self._hash_image(image_bytes)

            # Identical to previous frame -- no change
            if new_hash == self._last_hash:
                logger.debug("[%s] Screen unchanged, skipping", self.session_id[:8])
                return CaptureResult(outcome=CaptureOutcome.SKIPPED)

            # Record this change
            self._change_times.append(time.monotonic())
            self._last_hash = new_hash

            # Video detection
            if self._is_video():
                if not self._video_warned:
                    self._video_warned = True
                    apology = (
                        "I noticed a video is being played on screen. "
                        "I'm not able to process video content just yet -- "
                        "I'll resume capturing once the video stops. Sorry about that!"
                    )
                    # Also log it in context so LLM can reference it
                    self.context_manager.add_screen_content(
                        "[Notice] A video was playing on the shared screen. "
                        "Screen content extraction was paused."
                    )
                    logger.info("[%s] Video detected on shared screen", self.session_id[:8])
                    return CaptureResult(outcome=CaptureOutcome.VIDEO, apology=apology)
                return CaptureResult(outcome=CaptureOutcome.VIDEO)

            # Already captured earlier in this share; skip re-processing.
            if new_hash in self._seen_hashes:
                logger.debug("[%s] Screen previously captured, skipping", self.session_id[:8])
                return CaptureResult(outcome=CaptureOutcome.SKIPPED)

            # Mark as seen under lock before releasing — prevents duplicate extraction
            # if a concurrent call arrives with the same frame while we are awaiting Gemini.
            self._seen_hashes.add(new_hash)

            # No Gemini client configured — nothing to extract.
            if self.gemini is None:
                logger.warning(
                    "[%s] Gemini not configured, skipping extraction", self.session_id[:8]
                )
                return CaptureResult(outcome=CaptureOutcome.EMPTY)

        # --- Lock released --- Gemini extraction happens outside the lock so
        # that concurrent frames are not serialised on the slow API round-trip.
        content = await self.gemini.extract_screen_content(image_bytes)
        if not content.strip():
            return CaptureResult(outcome=CaptureOutcome.EMPTY)

        self.context_manager.add_screen_content(content)
        logger.info(
            "[%s] Screen content captured (%d chars)", self.session_id[:8], len(content)
        )
        return CaptureResult(outcome=CaptureOutcome.EXTRACTED, content=content)

    async def reset_for_new_share(self) -> None:
        """Reset state for a new screen share session (thread-safe).

        Called when participant_events.screenshare_on/off fires.
        Clears the hash and video detection state so the new share
        is processed independently from the previous one.
        """
        async with self._lock:
            self._last_hash = None
            self._seen_hashes.clear()
            self._change_times.clear()
            self._video_warned = False
            logger.debug("[%s] Screen capture state reset for new share", self.session_id[:8])
