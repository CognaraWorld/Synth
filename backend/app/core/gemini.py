"""Gemini Vision client for screen content extraction."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """You are analyzing a shared screen from a video meeting.

Extract all useful content visible on this screen. Be specific and thorough:
- Slides/presentations: extract slide title, all bullet points, text, and describe charts
- Documents: extract all readable text
- Code/terminals: extract code or command output exactly
- Web pages: extract main content and key data
- Spreadsheets: describe structure and key data

Return only the extracted content in clean structured text.
If the screen shows a loading state, blank screen, or nothing useful, return an empty string."""


class GeminiVisionClient:
    """Gemini Vision API client for screen content extraction.

    Uses google-genai SDK (same as llm.py). If the SDK is missing or the API
    key is not set, extraction silently returns empty string.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not (self._api_key or "").strip():
            return None
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
            return self._client
        except ImportError:
            logger.error(
                "google-genai not installed. "
                "Run: pip install google-genai"
            )
            return None

    async def extract_screen_content(self, image_bytes: bytes) -> str:
        """Extract text and content from a screenshot via Gemini Vision.

        Args:
            image_bytes: Raw PNG or JPEG image bytes.

        Returns:
            Extracted content string, or empty string on failure/no content.
        """
        client = self._get_client()
        if client is None:
            return ""

        try:
            from google import genai

            # Detect MIME type from magic bytes: JPEG starts with FF D8, PNG with 89 50 4E 47
            mime_type = "image/jpeg" if image_bytes[:2] == b"\xff\xd8" else "image/png"
            image_part = genai.types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            )

            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=[image_part, _EXTRACTION_PROMPT],
                    ),
                ),
                timeout=30.0,
            )

            content = response.text.strip() if response.text else ""
            logger.debug("Gemini extracted %d chars from screenshot", len(content))
            return content

        except Exception as exc:
            logger.error("Gemini screen extraction failed: %s", exc)
            return ""
