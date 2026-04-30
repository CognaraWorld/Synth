"""Regression tests: Deepgram phonetic mishearings of 'Nova' must trigger.

Real production transcripts captured these mishearings:
  - 'Inn over, what's up? How you'   (Hey Nova, what's up? How are you)
  - 'How are Nova?'                   (Hey Nova, how are you?)

The bare 'Nova' substring catches 'How are Nova', but 'Inn over' did not
match any variant in the original regex. This adds the observed variants
while guarding against false positives in unrelated phrases.
"""

from __future__ import annotations

import pytest

from app.utils.wake_word import detect


class TestNovaPhoneticVariants:
    @pytest.mark.parametrize(
        "transcript,expected_question",
        [
            ("Hey Nova, what's the weather?", "what's the weather?"),
            ("Nova, what time is it?", "what time is it?"),
            ("Hey Inn over, what's up?", "what's up?"),
            ("Hey In over, summarize the call", "summarize the call"),
            ("Hey Know va, give me the action items", "give me the action items"),
            ("Hey Noah, ping the team", "ping the team"),  # existing variant
            ("Hey Mova, status update", "status update"),  # existing variant
            ("Hey Nove, recap please", "recap please"),    # new variant
        ],
    )
    def test_known_variants_trigger(
        self, transcript: str, expected_question: str
    ) -> None:
        detected, question = detect(transcript)
        assert detected, f"Wake word should fire for {transcript!r}"
        assert expected_question in question, (
            f"Expected question text '{expected_question}' inside extracted "
            f"{question!r} for transcript {transcript!r}"
        )


class TestNovaFalsePositiveGuards:
    @pytest.mark.parametrize(
        "transcript",
        [
            # Bare ambiguous variants must NOT trigger without a wake prefix
            "I'm in over my head with this project",
            "We're in over our budget",
            "Just letting you know over coffee",
            # Word boundary still blocks compounds (kept from earlier fix)
            "supernova fans are everywhere",
            "the innovate team did great work",
        ],
    )
    def test_ambiguous_phrases_without_wake_prefix_stay_silent(
        self, transcript: str
    ) -> None:
        detected, _ = detect(transcript)
        assert not detected, (
            f"Wake word must NOT fire for {transcript!r} — ambiguous two-word "
            "variants like 'in over' require a wake prefix to disambiguate."
        )
