"""Regression tests for follow-up coherence detection."""

from __future__ import annotations


def test_has_coherence_marker_uses_word_boundaries() -> None:
    from app.utils.followup_markers import has_coherence_marker

    assert has_coherence_marker("bandwidth allocation today") is False
    assert has_coherence_marker("butter chicken later") is False
    assert has_coherence_marker("furthermore bandwidth planning") is False


def test_has_coherence_marker_keeps_real_followup_cues() -> None:
    from app.utils.followup_markers import has_coherence_marker

    assert has_coherence_marker("Tell me more about the budget") is True
    assert has_coherence_marker("what about the rollout plan") is True
    assert has_coherence_marker("could you explain the delay") is True
