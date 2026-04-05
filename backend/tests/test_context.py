"""Tests for the rolling summary and context manager modules.

Run all context tests::

    pytest tests/test_context.py

All tests are fast (no ML models, no network calls).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.context.rolling_summary import RollingSummary
from app.context.manager import ContextManager


# =====================================================================
# RollingSummary tests
# =====================================================================


class TestRollingSummaryInit:
    """Verify initial state of RollingSummary."""

    def test_init(self) -> None:
        rs = RollingSummary()
        assert rs.summary == ""
        assert rs._pending_text == ""
        assert rs.update_interval_chars == 500
        assert rs._llm_client is None

    def test_init_custom_interval(self) -> None:
        rs = RollingSummary(update_interval_chars=1000)
        assert rs.update_interval_chars == 1000


class TestRollingSummaryAccumulate:
    """Test text accumulation without an LLM client."""

    def test_accumulate_without_llm(self) -> None:
        """Chunks below the threshold should accumulate; summary stays empty."""
        rs = RollingSummary(update_interval_chars=100)
        asyncio.get_event_loop().run_until_complete(rs.update("short chunk"))
        assert rs._pending_text == "short chunk"
        assert rs.summary == ""

    def test_accumulate_above_threshold_without_llm(self) -> None:
        """Even past threshold, no LLM client means no summarization."""
        rs = RollingSummary(update_interval_chars=10)
        asyncio.get_event_loop().run_until_complete(rs.update("a" * 50))
        # Text should remain in pending because there is no LLM client.
        assert rs._pending_text == "a" * 50
        assert rs.summary == ""


class TestRollingSummaryGetSummary:
    """Test get_summary output under various states."""

    def test_get_summary_empty(self) -> None:
        rs = RollingSummary()
        assert rs.get_summary() == ""

    def test_get_summary_with_pending(self) -> None:
        """Pending text should appear in the get_summary output."""
        rs = RollingSummary()
        rs._pending_text = "some pending text"
        result = rs.get_summary()
        assert "[Recent, not yet summarized]" in result
        assert "some pending text" in result

    def test_get_summary_with_summary_only(self) -> None:
        rs = RollingSummary()
        rs.summary = "Key decision: use Python."
        assert rs.get_summary() == "Key decision: use Python."

    def test_get_summary_with_summary_and_pending(self) -> None:
        rs = RollingSummary()
        rs.summary = "Existing summary."
        rs._pending_text = "new stuff"
        result = rs.get_summary()
        assert result.startswith("Existing summary.")
        assert "new stuff" in result


class TestRollingSummaryWithLLM:
    """Test summarization when an LLM client is injected."""

    def test_update_calls_llm_above_threshold(self) -> None:
        rs = RollingSummary(update_interval_chars=10)

        mock_llm = MagicMock()
        mock_llm.query.return_value = "Updated meeting summary."
        rs.set_llm_client(mock_llm)

        asyncio.get_event_loop().run_until_complete(rs.update("A" * 20))

        mock_llm.query.assert_called_once()
        assert rs.summary == "Updated meeting summary."
        assert rs._pending_text == ""

    def test_update_does_not_call_llm_below_threshold(self) -> None:
        rs = RollingSummary(update_interval_chars=100)

        mock_llm = MagicMock()
        rs.set_llm_client(mock_llm)

        asyncio.get_event_loop().run_until_complete(rs.update("tiny"))

        mock_llm.query.assert_not_called()
        assert rs._pending_text == "tiny"

    def test_update_prompt_includes_current_summary(self) -> None:
        """The LLM prompt should include the existing summary."""
        rs = RollingSummary(update_interval_chars=5)
        rs.summary = "Previous summary content."

        mock_llm = MagicMock()
        mock_llm.query.return_value = "New summary."
        rs.set_llm_client(mock_llm)

        asyncio.get_event_loop().run_until_complete(rs.update("X" * 10))

        call_args = mock_llm.query.call_args
        prompt = call_args.kwargs.get("question") or call_args[1].get("question") or call_args[0][1]
        assert "Previous summary content." in prompt


class TestRollingSummaryHelpers:
    """Test helper methods."""

    def test_get_pending_length(self) -> None:
        rs = RollingSummary()
        assert rs.get_pending_length() == 0
        rs._pending_text = "hello"
        assert rs.get_pending_length() == 5

    def test_reset(self) -> None:
        rs = RollingSummary()
        rs.summary = "Some summary"
        rs._pending_text = "some pending"
        rs.reset()
        assert rs.summary == ""
        assert rs._pending_text == ""

    def test_reset_preserves_llm_client(self) -> None:
        """Reset should clear text but keep the LLM client reference."""
        rs = RollingSummary()
        mock_llm = MagicMock()
        rs.set_llm_client(mock_llm)
        rs.summary = "data"
        rs._pending_text = "pending"

        rs.reset()

        assert rs._llm_client is mock_llm
        assert rs.summary == ""
        assert rs._pending_text == ""


# =====================================================================
# ContextManager tests
# =====================================================================


class TestContextManagerInit:
    """Verify initial state of ContextManager."""

    def test_init(self) -> None:
        cm = ContextManager()
        assert cm.max_context_tokens == 8000
        assert cm.rolling_summary is not None
        assert cm.raw_buffer is not None
        assert cm.rag_pipeline is None

    def test_init_custom_tokens(self) -> None:
        cm = ContextManager(max_context_tokens=4000)
        assert cm.max_context_tokens == 4000


class TestContextManagerTokenCount:
    """Verify the rough token estimation."""

    def test_token_count_empty(self) -> None:
        cm = ContextManager()
        assert cm.get_token_count("") == 0

    def test_token_count_single_word(self) -> None:
        cm = ContextManager()
        assert cm.get_token_count("hello") == 1  # int(1 * 1.3) == 1

    def test_token_count_multiple_words(self) -> None:
        cm = ContextManager()
        text = "the quick brown fox jumps over the lazy dog"  # 9 words
        assert cm.get_token_count(text) == int(9 * 1.3)  # 11

    def test_token_count_returns_int(self) -> None:
        cm = ContextManager()
        result = cm.get_token_count("one two three")
        assert isinstance(result, int)


class TestContextManagerAddTranscript:
    """Test transcript ingestion."""

    def test_add_transcript(self) -> None:
        cm = ContextManager()
        cm.add_transcript("Hello everyone, let's begin.")
        recent = cm.raw_buffer.get_recent(minutes=5)
        assert "Hello everyone" in recent

    def test_add_transcript_with_timestamp(self) -> None:
        cm = ContextManager()
        ts = datetime.now(timezone.utc)  # Use current time so it's within buffer window
        cm.add_transcript("Specific time entry", timestamp=ts)
        full = cm.raw_buffer.get_full_text()
        assert "Specific time entry" in full

    def test_add_transcript_feeds_rolling_summary(self) -> None:
        cm = ContextManager()
        cm.add_transcript("Meeting notes here")
        # Pending text should appear in the rolling summary's pending buffer.
        assert cm.rolling_summary.get_pending_length() > 0

    def test_add_multiple_transcripts(self) -> None:
        cm = ContextManager()
        cm.add_transcript("First segment.")
        cm.add_transcript("Second segment.")
        recent = cm.raw_buffer.get_recent(minutes=5)
        assert "First segment." in recent
        assert "Second segment." in recent


class TestContextManagerAssembleContext:
    """Test context assembly output."""

    def test_assemble_context_empty(self) -> None:
        """All four sections should be present even when there is no data."""
        cm = ContextManager()
        result = cm.assemble_context(question="What was discussed?", session_id="s1")
        assert "=== MEETING SUMMARY ===" in result
        assert "=== RECENT CONVERSATION (last 5 minutes) ===" in result
        assert "=== DOCUMENT OVERVIEWS ===" in result
        assert "=== RELEVANT DOCUMENT PASSAGES ===" in result

    def test_assemble_context_with_buffer(self) -> None:
        cm = ContextManager()
        cm.add_transcript("We decided to use FastAPI for the backend.")
        result = cm.assemble_context(question="What framework?", session_id="s1")
        assert "FastAPI" in result

    def test_assemble_context_with_rag(self) -> None:
        cm = ContextManager()
        mock_rag = MagicMock()
        mock_rag.search.return_value = [
            {"text": "FastAPI docs excerpt", "metadata": {"filename": "api.pdf"}},
        ]
        cm.set_rag_pipeline(mock_rag)

        result = cm.assemble_context(question="How to set up API?", session_id="s1")
        assert "FastAPI docs excerpt" in result
        assert "[api.pdf]" in result
        mock_rag.search.assert_called_once_with(query="How to set up API?", top_k=5)

    def test_assemble_context_rag_failure_graceful(self) -> None:
        """A failing RAG pipeline should not crash assembly."""
        cm = ContextManager()
        mock_rag = MagicMock()
        mock_rag.search.side_effect = RuntimeError("Not initialized")
        cm.set_rag_pipeline(mock_rag)

        result = cm.assemble_context(question="test", session_id="s1")
        # Should still contain structural sections without crashing.
        assert "=== MEETING SUMMARY ===" in result

    def test_assemble_context_respects_token_budget(self) -> None:
        """Very long text should be truncated to fit the budget."""
        cm = ContextManager(max_context_tokens=50)
        # Add a large amount of text to the buffer.
        long_text = " ".join([f"word{i}" for i in range(500)])
        cm.raw_buffer.append(long_text)

        result = cm.assemble_context(question="test", session_id="s1")
        # The result should be meaningfully shorter than the raw input.
        result_tokens = cm.get_token_count(result)
        raw_tokens = cm.get_token_count(long_text)
        assert result_tokens < raw_tokens

    def test_assemble_context_without_rag(self) -> None:
        """When no RAG pipeline is set, the passages section is empty."""
        cm = ContextManager()
        cm.add_transcript("Some discussion content.")
        result = cm.assemble_context(question="test", session_id="s1")
        lines = result.split("\n")
        doc_idx = next(i for i, l in enumerate(lines) if "RELEVANT DOCUMENT PASSAGES" in l)
        assert lines[doc_idx + 1].strip() == ""

    def test_assemble_context_with_document_summaries(self) -> None:
        """Document summaries should appear in the DOCUMENT OVERVIEWS section."""
        cm = ContextManager()
        cm.add_document_summary("report.pdf", "Q3 revenue was $10M, up 23% YoY.")
        result = cm.assemble_context(question="test", session_id="s1")
        assert "Q3 revenue was $10M" in result
        assert "[report.pdf]" in result
        assert "=== DOCUMENT OVERVIEWS ===" in result

    def test_add_document_summary_ignores_empty(self) -> None:
        """Empty summaries should not be added."""
        cm = ContextManager()
        cm.add_document_summary("empty.pdf", "")
        cm.add_document_summary("blank.pdf", "   ")
        assert len(cm.document_summaries) == 0

    def test_reset_clears_document_summaries(self) -> None:
        """Reset should clear document summaries."""
        cm = ContextManager()
        cm.add_document_summary("report.pdf", "Some summary")
        cm.reset()
        assert len(cm.document_summaries) == 0


class TestContextManagerReset:
    """Test reset clears all layers."""

    def test_reset(self) -> None:
        cm = ContextManager()
        cm.add_transcript("Some transcript text")
        cm.rolling_summary.summary = "Some summary"
        cm.set_rag_pipeline(MagicMock())

        cm.reset()

        assert cm.rolling_summary.summary == ""
        assert cm.rolling_summary.get_pending_length() == 0
        assert len(cm.raw_buffer) == 0
        assert cm.rag_pipeline is None

    def test_reset_allows_reuse(self) -> None:
        """After reset, the manager should be usable for a new session."""
        cm = ContextManager()
        cm.add_transcript("Old session data.")
        cm.reset()

        cm.add_transcript("New session data.")
        recent = cm.raw_buffer.get_recent(minutes=5)
        assert "New session data." in recent
        assert "Old session data." not in recent
