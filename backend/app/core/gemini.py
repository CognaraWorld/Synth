"""Gemini Vision client for screen content extraction."""
from __future__ import annotations

import asyncio
import base64
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

    Uses google-generativeai SDK. If the SDK is missing or the API key
    is not set, extraction silently returns empty string.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._model = None

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            import google.generativeai as genai
            # Pass api_key directly to GenerativeModel via client instead of
            # genai.configure() which sets process-wide global state and causes
            # multi-session key collisions. The client kwarg is supported in
            # google-generativeai >= 0.5.0.
            try:
                import google.ai.generativelanguage as glm
                client = glm.GenerativeServiceClient(
                    client_options={"api_key": self._api_key}
                )
                self._model = genai.GenerativeModel(
                    "gemini-2.0-flash", client=client
                )
            except Exception:
                # Fallback for older SDK versions — configure globally
                genai.configure(api_key=self._api_key)
                self._model = genai.GenerativeModel("gemini-2.0-flash")
            return self._model
        except ImportError:
            logger.error(
                "google-generativeai not installed. "
                "Run: pip install google-generativeai"
            )
            return None

    async def extract_screen_content(self, image_bytes: bytes) -> str:
        """Extract text and content from a screenshot via Gemini Vision.

        Args:
            image_bytes: Raw PNG or JPEG image bytes.

        Returns:
            Extracted content string, or empty string on failure/no content.
        """
        model = self._get_model()
        if model is None:
            return ""

        try:
            import google.generativeai as genai

            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            # Detect MIME type from magic bytes: JPEG starts with FF D8, PNG with 89 50 4E 47
            mime_type = "image/jpeg" if image_bytes[:2] == b"\xff\xd8" else "image/png"
            image_part = {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_image,
                }
            }

            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: model.generate_content([image_part, _EXTRACTION_PROMPT]),
                ),
                timeout=30.0,
            )

            content = response.text.strip() if response.text else ""
            logger.debug("Gemini extracted %d chars from screenshot", len(content))
            return content

        except Exception as exc:
            logger.error("Gemini screen extraction failed: %s", exc)
            return ""
