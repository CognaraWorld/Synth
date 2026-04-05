"""Recall.ai API client.

Manages the lifecycle of virtual meeting bots through the Recall.ai
platform. Handles bot creation, audio streaming, meeting controls
(mute/unmute, hand raise), and status monitoring.

Phase 6 implementation.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, AsyncIterator

import httpx
from pydub import AudioSegment

from app.config import get_settings

logger = logging.getLogger(__name__)


class RecallClientError(Exception):
    """Base exception for Recall.ai client errors."""


class BotCreationError(RecallClientError):
    """Raised when bot deployment fails."""


class BotNotFoundError(RecallClientError):
    """Raised when a bot ID does not exist."""


class RecallClient:
    """Client for the Recall.ai bot management API.

    Provides methods for deploying bots into meetings, streaming audio
    bidirectionally, and controlling bot behavior within the meeting.

    Attributes:
        api_key: Recall.ai API key for authentication.
        base_url: Recall.ai API base URL.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Recall.ai client.

        Args:
            api_key: Recall.ai API key for authenticating requests.
                Falls back to ``settings.recall_api_key`` when not provided.
        """
        settings = get_settings()
        self.api_key = api_key or settings.recall_api_key
        region = settings.recall_region or "us-west-2"
        self.base_url = f"https://{region}.recall.ai/api/v1"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    # ------------------------------------------------------------------
    # Bot lifecycle
    # ------------------------------------------------------------------

    async def create_bot(
        self,
        meeting_url: str,
        bot_name: str = "Synth",
        webhook_url: str | None = None,
    ) -> str:
        """Deploy a new bot into a meeting.

        Args:
            meeting_url: The meeting URL (Zoom, Teams, or Meet).
            bot_name: Display name for the bot in the meeting.
            webhook_url: Public URL for real-time transcription delivery.

        Returns:
            The unique bot ID assigned by Recall.ai.

        Raises:
            BotCreationError: If the API request fails.
        """
        payload: dict = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
        }

        if webhook_url:
            settings = get_settings()
            transcript_provider: dict = {"meeting_captions": {}}
            if settings.deepgram_api_key:
                transcript_provider = {
                    "deepgram_streaming": {
                        "api_key": settings.deepgram_api_key,
                        "extra_params": {
                            "model": "nova-3",
                            "smart_format": "true",
                            "punctuate": "true",
                            "diarize": "true",
                            "keywords": "Nova:5,Hey Nova:5,nova:5",
                            "utterances": "true",
                            "utterance_end_ms": "700",
                        },
                    },
                }
            payload["recording_config"] = {
                "transcript": {
                    "provider": transcript_provider,
                },
                "realtime_endpoints": [
                    {
                        "type": "webhook",
                        "url": webhook_url,
                        "events": ["transcript.data"],
                    },
                ],
            }
            # Enable screen capture for OCR-based context enrichment
            payload["output_media"] = {
                "camera": {"kind": "jpeg", "size": {"width": 1280, "height": 720}},
            }

        try:
            response = await self._client.post("/bot", json=payload)
            response.raise_for_status()
            data = response.json()
            bot_id: str = data["id"]
            logger.info("Created Recall.ai bot %s for meeting %s", bot_id, meeting_url)
            return bot_id
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Bot creation failed (HTTP %d): %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise BotCreationError(
                f"Failed to create bot: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Bot creation failed (network): %s", exc)
            raise BotCreationError(f"Failed to create bot: {exc}") from exc

    async def get_bot_status(self, bot_id: str) -> dict[str, Any]:
        """Get the current status of a deployed bot.

        Args:
            bot_id: The Recall.ai bot identifier.

        Returns:
            Dictionary with bot status including status_changes,
            meeting_metadata, and participant details.

        Raises:
            BotNotFoundError: If the bot ID does not exist.
            RecallClientError: On network or unexpected errors.
        """
        try:
            response = await self._client.get(f"/bot/{bot_id}")
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return {
                "id": data.get("id"),
                "status_changes": data.get("status_changes", []),
                "meeting_metadata": data.get("meeting_metadata", {}),
                "meeting_url": data.get("meeting_url", ""),
                "bot_name": data.get("bot_name", ""),
                "transcripts": data.get("transcripts", []),
            }
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Bot %s not found", bot_id)
                raise BotNotFoundError(f"Bot {bot_id} not found") from exc
            logger.error(
                "Bot status check failed (HTTP %d): %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise RecallClientError(
                f"Failed to get bot status: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Bot status check failed (network): %s", exc)
            raise RecallClientError(f"Failed to get bot status: {exc}") from exc

    async def stop_bot(self, bot_id: str) -> None:
        """Remove the bot from the meeting.

        Sends a leave request to the Recall.ai API. Gracefully handles
        cases where the bot has already left or doesn't exist.

        Args:
            bot_id: The Recall.ai bot identifier.
        """
        try:
            response = await self._client.post(f"/bot/{bot_id}/leave")
            response.raise_for_status()
            logger.info("Stopped Recall.ai bot %s", bot_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning(
                    "Bot %s already gone or not found during stop", bot_id
                )
                return
            # 400 may indicate bot already left — treat as non-fatal
            if exc.response.status_code == 400:
                logger.warning(
                    "Bot %s stop returned 400 (may have already left): %s",
                    bot_id,
                    exc.response.text,
                )
                return
            logger.error(
                "Failed to stop bot %s (HTTP %d): %s",
                bot_id,
                exc.response.status_code,
                exc.response.text,
            )
        except httpx.HTTPError as exc:
            logger.error("Failed to stop bot %s (network): %s", bot_id, exc)

    # ------------------------------------------------------------------
    # Audio streaming (placeholder — real impl requires WebSocket)
    # ------------------------------------------------------------------

    async def get_audio_stream(self, bot_id: str) -> AsyncIterator[bytes]:
        """Open a real-time audio stream from the meeting.

        Yields audio frames from all meeting participants as raw PCM bytes.

        Args:
            bot_id: The Recall.ai bot identifier.

        Yields:
            Raw audio bytes (PCM, 16-bit, 16kHz mono) from the meeting.

        Note:
            This is a placeholder implementation. The production version
            requires a WebSocket connection to Recall.ai's real-time
            audio endpoint. The WebSocket URL is typically returned in
            the bot creation response or obtained via a separate API call.

            TODO: Replace with WebSocket-based implementation:
            1. Connect to ``wss://api.recall.ai/bot/{bot_id}/audio/ws``
            2. Authenticate via the token in the connection handshake
            3. Yield incoming binary frames as PCM audio chunks
            4. Handle reconnection on transient failures
        """
        logger.warning(
            "get_audio_stream is a placeholder — real-time audio "
            "requires WebSocket integration with Recall.ai"
        )
        # Placeholder: fetch any available audio via REST as a fallback
        try:
            response = await self._client.get(f"/bot/{bot_id}/audio")
            if response.status_code == 200:
                yield response.content
        except httpx.HTTPError as exc:
            logger.error("Audio stream fetch failed for bot %s: %s", bot_id, exc)

    @staticmethod
    def pcm_to_mp3_b64(audio_bytes: bytes) -> str:
        """Convert raw PCM audio to base64-encoded MP3."""
        audio_seg = AudioSegment(
            data=audio_bytes,
            sample_width=2,
            frame_rate=24000,
            channels=1,
        )
        mp3_buf = io.BytesIO()
        audio_seg.export(mp3_buf, format="mp3", bitrate="64k")
        return base64.b64encode(mp3_buf.getvalue()).decode("ascii")

    async def send_audio(self, bot_id: str, audio_bytes: bytes) -> None:
        """Send audio into the meeting (bot speaks).

        Args:
            bot_id: The Recall.ai bot identifier.
            audio_bytes: Raw audio bytes (PCM int16, 24kHz mono).
        """
        b64_audio = self.pcm_to_mp3_b64(audio_bytes)

        try:
            response = await self._client.post(
                f"/bot/{bot_id}/output_audio",
                json={
                    "kind": "mp3",
                    "b64_data": b64_audio,
                },
            )
            response.raise_for_status()
            logger.info("Sent %d audio bytes to bot %s", len(audio_bytes), bot_id)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Send audio failed for bot %s (HTTP %d): %s",
                bot_id,
                exc.response.status_code,
                exc.response.text[:200],
            )
        except httpx.HTTPError as exc:
            logger.error("Send audio failed for bot %s (network): %s", bot_id, exc)

    # ------------------------------------------------------------------
    # Meeting controls
    # ------------------------------------------------------------------

    async def send_audio_b64(self, bot_id: str, b64_audio: str) -> None:
        """Send pre-encoded base64 MP3 audio into the meeting."""
        try:
            response = await self._client.post(
                f"/bot/{bot_id}/output_audio",
                json={"kind": "mp3", "b64_data": b64_audio},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Send audio failed for bot %s (HTTP %d): %s",
                bot_id, exc.response.status_code, exc.response.text[:200],
            )
        except httpx.HTTPError as exc:
            logger.error("Send audio failed for bot %s (network): %s", bot_id, exc)

    async def stop_audio(self, bot_id: str) -> None:
        """Stop any currently playing audio output immediately."""
        try:
            response = await self._client.post(f"/bot/{bot_id}/stop_output_audio")
            response.raise_for_status()
            logger.info("Stopped audio output for bot %s", bot_id)
        except httpx.HTTPStatusError as exc:
            # 400/404 = nothing playing or bot not found — non-fatal
            if exc.response.status_code not in (400, 404):
                logger.error("Stop audio failed for bot %s: %s", bot_id, exc.response.text[:200])
        except httpx.HTTPError as exc:
            logger.error("Stop audio failed for bot %s: %s", bot_id, exc)

    async def raise_hand(self, bot_id: str) -> None:
        """Raise the bot's hand. Skipped — not supported in all regions."""
        logger.debug("Raise hand (skipped) for bot %s", bot_id)

    async def mute(self, bot_id: str) -> None:
        """Mute the bot. No-op — bot only speaks via output_audio calls."""
        logger.debug("Mute (no-op) for bot %s", bot_id)

    async def unmute(self, bot_id: str) -> None:
        """Unmute the bot. No-op — bot only speaks via output_audio calls."""
        logger.debug("Unmute (no-op) for bot %s", bot_id)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying httpx client and release resources."""
        await self._client.aclose()
        logger.debug("Recall.ai client closed")
