"""Kokoro Text-to-Speech (TTS) wrapper.

Converts text responses into natural-sounding audio bytes that can be
streamed back into the meeting via the Recall.ai bot. Also generates
filler responses ("Let me think about that...") to reduce perceived latency.

Backed by kokoro-onnx — same model and voices as the original Kokoro
package but runs via ONNX Runtime. Avoids the PydanticSchemaGenerationError
the torch-based package throws with pydantic 2.10, and is typically
20-30% faster per synthesis.
"""

from __future__ import annotations

import io
import logging
import os
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    from kokoro_onnx import Kokoro
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    Kokoro = None


# Default model-file locations relative to the backend package root.
# Overridable via KOKORO_ONNX_MODEL_PATH / KOKORO_ONNX_VOICES_PATH env vars
# so the same code works in Docker where files live at a different path.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_MODEL_PATH = _BACKEND_ROOT / "models" / "kokoro" / "kokoro-v1.0.onnx"
_DEFAULT_VOICES_PATH = _BACKEND_ROOT / "models" / "kokoro" / "voices-v1.0.bin"


class TextToSpeech:
    """Wrapper around Kokoro TTS for speech synthesis.

    Generates audio bytes from text, supporting both full responses
    and quick filler phrases for latency masking.

    Attributes:
        voice: Voice profile identifier.
        sample_rate: Output audio sample rate in Hz.
        speed: Speech speed multiplier (1.0 = normal).
    """

    def __init__(
        self,
        voice: str = "af_heart",
        sample_rate: int = 24000,
        speed: float = 1.0,
    ) -> None:
        """Initialize the Kokoro TTS engine.

        Args:
            voice: Voice profile to use for synthesis. Kokoro voices use
                codes like ``af_heart`` (American female) or ``am_adam``
                (American male).
            sample_rate: Desired output sample rate in Hz. Kokoro natively
                outputs at 24000 Hz — resampling is NOT applied; callers
                should request 24000.
            speed: Speech speed multiplier. Values > 1.0 are faster.
        """
        self.voice = voice
        self.sample_rate = sample_rate
        self.speed = speed

        model_path = os.environ.get("KOKORO_ONNX_MODEL_PATH", str(_DEFAULT_MODEL_PATH))
        voices_path = os.environ.get("KOKORO_ONNX_VOICES_PATH", str(_DEFAULT_VOICES_PATH))

        self._pipeline = None
        if Kokoro is None:
            logger.warning("kokoro-onnx not installed; TTS will return empty audio")
            return
        if not Path(model_path).exists() or not Path(voices_path).exists():
            logger.warning(
                "Kokoro ONNX files missing (model=%s, voices=%s); TTS disabled",
                model_path, voices_path,
            )
            return
        try:
            self._pipeline = Kokoro(model_path, voices_path)
            logger.info("Kokoro ONNX TTS initialized (voice=%s, speed=%.2fx)", voice, speed)
        except Exception as exc:
            logger.error("Kokoro ONNX init failed: %s", exc)
            self._pipeline = None

    def synthesize(self, text: str) -> bytes:
        """Convert text to speech audio.

        Args:
            text: The text to synthesize into audio.

        Returns:
            Raw audio bytes (PCM int16 format at 24 kHz) suitable for
            streaming into the meeting via Recall.ai. Returns empty bytes
            if TTS is unavailable or the input is empty.
        """
        if self._pipeline is None or not text or not text.strip():
            return b""

        try:
            samples, _sr = self._pipeline.create(
                text,
                voice=self.voice,
                speed=self.speed,
                lang="en-us",
            )
        except Exception as exc:
            logger.error("Kokoro synthesis failed: %s", exc)
            return b""

        if samples is None or len(samples) == 0:
            return b""

        # samples is a float32 numpy array in [-1.0, 1.0]; convert to PCM int16.
        clipped = np.clip(samples, -1.0, 1.0)
        pcm_int16 = (clipped * 32767).astype(np.int16)
        return pcm_int16.tobytes()

    def synthesize_to_wav(self, text: str) -> bytes:
        """Convert text to a complete WAV file.

        Args:
            text: The text to synthesize into audio.

        Returns:
            A complete WAV file as bytes with proper headers, suitable
            for saving to disk or sending over HTTP.
        """
        pcm_data = self.synthesize(text)
        if not pcm_data:
            return b""

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes per sample
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()
