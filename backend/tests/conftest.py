"""Shared fixtures and configuration for the Synth test suite."""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests that require ML models (VAD/STT) and are slow to run",
    )


@pytest.fixture()
def silent_audio_path(tmp_path: Path) -> Path:
    """Create a temporary WAV file containing 1 second of silence at 16 kHz mono.

    The file uses 16-bit PCM encoding with all zero samples, which represents
    digital silence. Useful for testing VAD (should return False) and verifying
    the pipeline handles empty audio without crashing.

    Returns:
        Path to the generated WAV file.
    """
    sample_rate = 16000
    num_channels = 1
    bits_per_sample = 16
    num_samples = sample_rate  # 1 second
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = num_samples * block_align

    wav_path = tmp_path / "silence.wav"
    with wav_path.open("wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))  # file size - 8
        f.write(b"WAVE")

        # fmt sub-chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # sub-chunk size (PCM)
        f.write(struct.pack("<H", 1))  # audio format (1 = PCM)
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))

        # data sub-chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)

    return wav_path


@pytest.fixture()
def noise_audio_path(tmp_path: Path) -> Path:
    """Create a temporary WAV file with 1 second of pseudo-random noise at 16 kHz.

    Generates deterministic noise (seeded RNG) so tests are reproducible.
    Useful for verifying VAD behavior with non-silent input.

    Returns:
        Path to the generated WAV file.
    """
    import random as _random

    rng = _random.Random(42)

    sample_rate = 16000
    num_channels = 1
    bits_per_sample = 16
    num_samples = sample_rate
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = num_samples * block_align

    wav_path = tmp_path / "noise.wav"
    with wav_path.open("wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")

        # fmt sub-chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))

        # data sub-chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        for _ in range(num_samples):
            sample = rng.randint(-32768, 32767)
            f.write(struct.pack("<h", sample))

    return wav_path
