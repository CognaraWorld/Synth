"""Screen share OCR and visual analysis.

Extracts text content from screen share screenshots captured during
meetings. Uses OCR to convert visual content (slides, documents, code)
into text that can be included in the LLM context window.

Primary: Gemini Flash (fast, free tier friendly).
Fallback: Claude Haiku vision (reliable, higher quality).

Phase 5 implementation.
"""

from __future__ import annotations

import base64
import logging

from app.config import get_settings

try:
    from google import genai
except ModuleNotFoundError:  # pragma: no cover
    genai = None

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover
    anthropic = None

logger = logging.getLogger(__name__)

_VISION_PROMPT = (
    "Extract all visible text from this screenshot. "
    "Return only the text content, preserving layout where possible."
)

_CLAUDE_VISION_MODEL = "claude-haiku-4-5-20251001"


class VisionProcessor:
    """Processes screen share screenshots for text extraction.

    Captures periodic screenshots from screen share streams and extracts
    text content via OCR for inclusion in meeting context.

    Primary: Gemini Flash via google.genai.Client.
    Fallback: Claude Haiku vision via Anthropic SDK.

    Attributes:
        ocr_engine: The OCR backend identifier.
    """

    def __init__(self, ocr_engine: str = "auto") -> None:
        """Initialize the vision processor.

        Args:
            ocr_engine: OCR backend identifier. "auto" tries Gemini first,
                then Claude. "gemini" or "claude-vision" force a specific backend.
        """
        self.ocr_engine = ocr_engine
        settings = get_settings()

        # Gemini setup (primary)
        self._gemini_client = None
        self._gemini_model = "gemini-2.5-flash-lite"
        if genai and settings.gemini_api_key:
            self._gemini_client = genai.Client(api_key=settings.gemini_api_key)

        # Claude setup (fallback)
        self._claude_client = None
        self._claude_async = None
        if anthropic and settings.anthropic_api_key:
            self._claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            self._claude_async = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

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

    def _gemini_extract(self, screenshot_bytes: bytes) -> str:
        """Extract text using Gemini vision."""
        if self._gemini_client is None:
            return ""
        try:
            encoded = base64.standard_b64encode(screenshot_bytes).decode("ascii")
            media_type = self._detect_media_type(screenshot_bytes)
            response = self._gemini_client.models.generate_content(
                model=self._gemini_model,
                contents=[
                    {
                        "parts": [
                            {"inline_data": {"mime_type": media_type, "data": encoded}},
                            {"text": _VISION_PROMPT},
                        ]
                    }
                ],
                config={
                    "system_instruction": "You are an OCR text extractor.",
                    "max_output_tokens": 4096,
                },
            )
            return response.text
        except Exception as exc:
            logger.warning("Gemini vision failed: %s", exc)
            return ""

    def _claude_extract(self, screenshot_bytes: bytes) -> str:
        """Extract text using Claude vision (sync)."""
        if self._claude_client is None:
            return ""
        try:
            encoded = base64.standard_b64encode(screenshot_bytes).decode("ascii")
            media_type = self._detect_media_type(screenshot_bytes)
            response = self._claude_client.messages.create(
                model=_CLAUDE_VISION_MODEL,
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
            logger.warning("Claude vision failed: %s", exc)
            return ""

    def extract_text(self, screenshot_bytes: bytes) -> str:
        """Extract text content from a screenshot image.

        Tries Gemini first (fast), falls back to Claude (reliable).

        Args:
            screenshot_bytes: Raw image bytes (PNG or JPEG format).

        Returns:
            Extracted text content from the screenshot. Empty string on error.
        """
        # Try Gemini first
        if self._gemini_client:
            result = self._gemini_extract(screenshot_bytes)
            if result and result.strip():
                return result

        # Fallback to Claude
        return self._claude_extract(screenshot_bytes)

    async def async_extract_text(self, screenshot_bytes: bytes) -> str:
        """Extract text content from a screenshot asynchronously.

        Tries Gemini first (via executor), falls back to Claude async.

        Args:
            screenshot_bytes: Raw image bytes (PNG or JPEG format).

        Returns:
            Extracted text content. Empty string on error.
        """
        # Try Gemini first (sync SDK in executor)
        if self._gemini_client:
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, self._gemini_extract, screenshot_bytes
                )
                if result and result.strip():
                    return result
            except Exception as exc:
                logger.warning("Gemini async vision failed: %s", exc)

        # Fallback to Claude async
        if self._claude_async is None:
            return ""

        try:
            encoded = base64.standard_b64encode(screenshot_bytes).decode("ascii")
            media_type = self._detect_media_type(screenshot_bytes)
            response = await self._claude_async.messages.create(
                model=_CLAUDE_VISION_MODEL,
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
            logger.error("Async vision text extraction failed: %s", exc)
            return ""
