"""Screen share OCR and visual analysis.

Extracts text content from screen share screenshots captured during
meetings. Uses OCR to convert visual content (slides, documents, code)
into text that can be included in the LLM context window.

Phase 5 implementation.
"""

from __future__ import annotations

import base64
import logging

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)

_VISION_PROMPT = (
    "Extract all visible text from this screenshot. "
    "Return only the text content, preserving layout where possible."
)

_VISION_MODEL = "claude-haiku-4-5-20251001"


class VisionProcessor:
    """Processes screen share screenshots for text extraction.

    Captures periodic screenshots from screen share streams and extracts
    text content via OCR for inclusion in meeting context.

    Attributes:
        ocr_engine: The OCR backend to use for text extraction.
    """

    def __init__(self, ocr_engine: str = "claude-vision") -> None:
        """Initialize the vision processor.

        Args:
            ocr_engine: OCR backend identifier. Supported: "tesseract",
                "claude-vision" (uses Claude's vision capabilities).
        """
        self.ocr_engine = ocr_engine

        if self.ocr_engine == "claude-vision":
            settings = get_settings()
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            self._async_client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
            )

    def _detect_media_type(self, screenshot_bytes: bytes) -> str:
        """Detect the image media type from its magic bytes.

        Args:
            screenshot_bytes: Raw image bytes.

        Returns:
            MIME type string (e.g. ``"image/png"``). Defaults to
            ``"image/png"`` if the format cannot be determined.
        """
        if screenshot_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if screenshot_bytes[:2] in (b"\xff\xd8",):
            return "image/jpeg"
        if screenshot_bytes[:4] == b"RIFF" and screenshot_bytes[8:12] == b"WEBP":
            return "image/webp"
        if screenshot_bytes[:3] == b"GIF":
            return "image/gif"
        return "image/png"

    def extract_text(self, screenshot_bytes: bytes) -> str:
        """Extract text content from a screenshot image.

        Args:
            screenshot_bytes: Raw image bytes (PNG or JPEG format) from
                a screen share capture.

        Returns:
            Extracted text content from the screenshot. Returns empty
            string if no text is detected or on error.
        """
        if self.ocr_engine != "claude-vision":
            logger.warning("OCR engine %r is not supported", self.ocr_engine)
            return ""

        try:
            encoded = base64.standard_b64encode(screenshot_bytes).decode("ascii")
            media_type = self._detect_media_type(screenshot_bytes)

            response = self._client.messages.create(
                model=_VISION_MODEL,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": encoded,
                                },
                            },
                            {
                                "type": "text",
                                "text": _VISION_PROMPT,
                            },
                        ],
                    },
                ],
            )
            return response.content[0].text
        except Exception as exc:
            logger.error("Vision text extraction failed: %s", exc)
            return ""

    async def async_extract_text(self, screenshot_bytes: bytes) -> str:
        """Extract text content from a screenshot asynchronously.

        Behaves identically to ``extract_text`` but uses the async
        Anthropic client, making it suitable for async request handlers.

        Args:
            screenshot_bytes: Raw image bytes (PNG or JPEG format) from
                a screen share capture.

        Returns:
            Extracted text content from the screenshot. Returns empty
            string if no text is detected or on error.
        """
        if self.ocr_engine != "claude-vision":
            logger.warning("OCR engine %r is not supported", self.ocr_engine)
            return ""

        try:
            encoded = base64.standard_b64encode(screenshot_bytes).decode("ascii")
            media_type = self._detect_media_type(screenshot_bytes)

            response = await self._async_client.messages.create(
                model=_VISION_MODEL,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": encoded,
                                },
                            },
                            {
                                "type": "text",
                                "text": _VISION_PROMPT,
                            },
                        ],
                    },
                ],
            )
            return response.content[0].text
        except Exception as exc:
            logger.error("Async vision text extraction failed: %s", exc)
            return ""
