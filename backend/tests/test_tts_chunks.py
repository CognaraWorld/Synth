"""Tests for word-boundary TTS chunking."""

from __future__ import annotations

from app.utils.tts_chunks import split_text_for_tts


def test_short_text_single_chunk() -> None:
    assert split_text_for_tts("Hello world.") == ["Hello world."]


def test_splits_long_sentence_on_spaces() -> None:
    words = ["word"] * 80
    text = " ".join(words) + "."
    chunks = split_text_for_tts(text, max_chars=50, min_space_break=10)
    assert len(chunks) >= 2
    assert all(len(c) <= 50 for c in chunks)
    joined = " ".join(chunks)
    assert "word" in joined


def test_empty() -> None:
    assert split_text_for_tts("") == []
    assert split_text_for_tts("   ") == []


def test_prefers_early_space_over_mid_word_cut() -> None:
    text = "short words " + ("x" * 45)
    chunks = split_text_for_tts(text, max_chars=25, min_space_break=20)

    assert chunks[0] == "short words"
    assert all(chunk for chunk in chunks)
