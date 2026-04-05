"""Screen share OCR and visual analysis.

Extracts text content from screen share screenshots captured during
meetings. Uses Gemini Flash vision for cheap, fast OCR. Falls back
to Claude vision if Gemini is unavailable.

Phase 5 implementation (updated: Gemini primary).
"""

from __future__ import annotations

import base64
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from google import genai
except ModuleNotFoundError:
    genai = None

try:
    import anthropic
except ModuleNotFoundError:
    anthropic = None

_VISION_PROMPT = (
    "Extract all visible text from this screenshot. "
    "Preserve layout, tables, and structure where possible. "
    "If there are charts or diagrams, describe what they show."
)


class VisionProcessor:
    """Processes screen share screenshots for text extraction.

    Uses Gemini Flash vision (primary) for cheap, fast OCR.
    Falls back to Claude vision if Gemini is unavailable.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._gemini_client = None
        self._claude_async = None

        if genai and settings.gemini_api_key:
            self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
            logger.info("VisionProcessor using Gemini Flash")
        elif anthropic and settings.anthropic_api_key:
            self._claude_async = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            logger.info("VisionProcessor using Claude vision (fallback)")

    def _detect_media_type(self, screenshot_bytes: bytes) -> str:
        """Detect image MIME type from magic bytes."""
        if screenshot_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if screenshot_bytes[:2] in (b"\xff\xd8",):
            return "image/jpeg"
        if screenshot_bytes[:4] == b"RIFF" and screenshot_bytes[8:12] == b"WEBP":
            return "image/webp"
        if screenshot_bytes[:3] == b"GIF":
            return "image/gif"
        return "image/png"

    async def async_extract_text(self, screenshot_bytes: bytes) -> str:
        """Extract text from a screenshot image.

        Args:
            screenshot_bytes: Raw image bytes (PNG/JPEG).

        Returns:
            Extracted text content. Empty string on error.
        """
        if not screenshot_bytes:
            return ""

        encoded = base64.standard_b64encode(screenshot_bytes).decode("ascii")
        media_type = self._detect_media_type(screenshot_bytes)

        # Try Gemini first
        if self._gemini_client:
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._gemini_client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=[
                            {
                                "parts": [
                                    {"inline_data": {"mime_type": media_type, "data": encoded}},
                                    {"text": _VISION_PROMPT},
                                ]
                            }
                        ],
                        config={"max_output_tokens": 4096},
                    ),
                )
                return response.text
            except Exception as exc:
                logger.warning("Gemini vision failed: %s", exc)

        # Fallback to Claude
        if self._claude_async:
            try:
                response = await self._claude_async.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4096,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
                            {"type": "text", "text": _VISION_PROMPT},
                        ],
                    }],
                )
                return response.content[0].text
            except Exception as exc:
                logger.error("Claude vision failed: %s", exc)

        return ""
