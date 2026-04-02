"""Recall.ai API client.

Manages the lifecycle of virtual meeting bots through the Recall.ai
platform. Handles bot creation, audio streaming, meeting controls
(mute/unmute, hand raise), and status monitoring.

Phase 6 implementation.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import httpx

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
        self.base_url = "https://api.recall.ai/api/v1"

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

    async def create_bot(self, meeting_url: str, bot_name: str = "Synth") -> str:
        """Deploy a new bot into a meeting.

        Args:
            meeting_url: The meeting URL (Zoom, Teams, or Meet).
            bot_name: Display name for the bot in the meeting.

        Returns:
            The unique bot ID assigned by Recall.ai.

        Raises:
            BotCreationError: If the API request fails.
        """
        payload = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "transcription_options": {"provider": "default"},
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

    async def send_audio(self, bot_id: str, audio_bytes: bytes) -> None:
        """Send audio into the meeting (bot speaks).

        Args:
            bot_id: The Recall.ai bot identifier.
            audio_bytes: Raw audio bytes (PCM format) to play in the meeting.

        Note:
            This is a placeholder implementation. The production version
            requires sending audio frames over the same WebSocket
            connection used for receiving audio.

            TODO: Replace with WebSocket-based implementation:
            1. Use the existing WebSocket connection from get_audio_stream
            2. Send binary frames with PCM audio data
            3. Respect the connection's flow control / backpressure
            4. Handle the case where the bot is muted
        """
        try:
            response = await self._client.post(
                f"/bot/{bot_id}/send_audio",
                content=audio_bytes,
                headers={"Content-Type": "audio/raw"},
            )
            response.raise_for_status()
            logger.debug("Sent %d audio bytes to bot %s", len(audio_bytes), bot_id)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Send audio failed for bot %s (HTTP %d): %s",
                bot_id,
                exc.response.status_code,
                exc.response.text,
            )
        except httpx.HTTPError as exc:
            logger.error("Send audio failed for bot %s (network): %s", bot_id, exc)

    # ------------------------------------------------------------------
    # Meeting controls
    # ------------------------------------------------------------------

    async def raise_hand(self, bot_id: str) -> None:
        """Raise the bot's hand in the meeting.

        Used as a visual indicator before the bot speaks. If the Recall.ai
        ``raise_hand`` endpoint is not available, falls back to sending
        a reaction emoji as a visual cue.

        Args:
            bot_id: The Recall.ai bot identifier.
        """
        try:
            # Try the dedicated raise_hand endpoint first
            response = await self._client.post(f"/bot/{bot_id}/raise_hand")
            response.raise_for_status()
            logger.debug("Raised hand for bot %s", bot_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Endpoint doesn't exist — fall back to reaction/emoji
                logger.debug(
                    "raise_hand endpoint not found for bot %s, "
                    "trying reaction fallback",
                    bot_id,
                )
                await self._send_reaction(bot_id, "raise_hand")
            else:
                logger.warning(
                    "raise_hand failed for bot %s (HTTP %d): %s",
                    bot_id,
                    exc.response.status_code,
                    exc.response.text,
                )
        except httpx.HTTPError as exc:
            logger.warning("raise_hand failed for bot %s (network): %s", bot_id, exc)

    async def _send_reaction(self, bot_id: str, reaction: str) -> None:
        """Send a reaction emoji via the bot.

        Fallback mechanism when a dedicated endpoint (e.g. raise_hand)
        is not available in the Recall.ai API.

        Args:
            bot_id: The Recall.ai bot identifier.
            reaction: Reaction type string (e.g. "raise_hand", "thumbs_up").
        """
        try:
            response = await self._client.post(
                f"/bot/{bot_id}/react",
                json={"reaction": reaction},
            )
            response.raise_for_status()
            logger.debug("Sent reaction %r for bot %s", reaction, bot_id)
        except httpx.HTTPError as exc:
            logger.warning(
                "Reaction %r failed for bot %s: %s", reaction, bot_id, exc
            )

    async def mute(self, bot_id: str) -> None:
        """Mute the bot's microphone.

        Args:
            bot_id: The Recall.ai bot identifier.
        """
        try:
            response = await self._client.post(
                f"/bot/{bot_id}/output_audio",
                json={"muted": True},
            )
            response.raise_for_status()
            logger.debug("Muted bot %s", bot_id)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Mute failed for bot %s (HTTP %d): %s",
                bot_id,
                exc.response.status_code,
                exc.response.text,
            )
        except httpx.HTTPError as exc:
            logger.warning("Mute failed for bot %s (network): %s", bot_id, exc)

    async def unmute(self, bot_id: str) -> None:
        """Unmute the bot's microphone.

        Args:
            bot_id: The Recall.ai bot identifier.
        """
        try:
            response = await self._client.post(
                f"/bot/{bot_id}/output_audio",
                json={"muted": False},
            )
            response.raise_for_status()
            logger.debug("Unmuted bot %s", bot_id)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Unmute failed for bot %s (HTTP %d): %s",
                bot_id,
                exc.response.status_code,
                exc.response.text,
            )
        except httpx.HTTPError as exc:
            logger.warning("Unmute failed for bot %s (network): %s", bot_id, exc)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying httpx client and release resources."""
        await self._client.aclose()
        logger.debug("Recall.ai client closed")
