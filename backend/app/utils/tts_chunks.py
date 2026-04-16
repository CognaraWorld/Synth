"""Split long TTS lines on word boundaries for smoother playback."""

from __future__ import annotations


def split_text_for_tts(
    text: str,
    max_chars: int = 200,
    min_space_break: int = 24,
) -> list[str]:
    """Split *text* into chunks no longer than *max_chars*, preferring spaces.

    Short strings are returned as a single chunk. Used when the LLM yields
    a long sentence that would otherwise be synthesized as one heavy clip.
    """
    s = (text or "").strip()
    if not s:
        return []
    if len(s) <= max_chars:
        return [s]

    chunks: list[str] = []
    remaining = s
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        window = remaining[:max_chars]
        cut = window.rfind(" ")
        if cut == -1:
            cut = max_chars
        elif cut < min_space_break:
            # Prefer an earlier word boundary over slicing a word in half.
            cut = cut if cut > 0 else max_chars
        piece = remaining[:cut].strip()
        if piece:
            chunks.append(piece)
        remaining = remaining[cut:].strip()
    return chunks
