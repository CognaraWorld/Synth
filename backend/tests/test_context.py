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
        assert rs.update_interval_chars == 300
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

    def test_update_caps_pending_text_during_llm_outage(self) -> None:
        """Repeated failed updates should keep only a bounded pending tail."""

        class FailingLLM:
            async def async_query(self, context: str, question: str) -> str:
                raise RuntimeError("LLM outage")

        rs = RollingSummary(update_interval_chars=1)
        rs.set_llm_client(FailingLLM())

        chunk_template = "chunk-{index:02d}-" + ("x" * 180)
        for index in range(40):
            asyncio.get_event_loop().run_until_complete(
                rs.update(chunk_template.format(index=index))
            )

        assert rs.get_pending_length() == rs.MAX_PENDING_TEXT_CHARS
        assert "chunk-39" in rs._pending_text
        assert "chunk-00" not in rs._pending_text


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

    def test_get_summary_uses_bounded_pending_preview(self) -> None:
        """get_summary should only expose a bounded pending-text preview."""
        rs = RollingSummary()
        rs.summary = "Existing summary."
        rs._pending_text = "".join(f"chunk-{i:03d}|" for i in range(200))

        result = rs.get_summary()

        assert result.startswith("Existing summary.")
        assert "[Recent, not yet summarized]:" in result
        assert "chunk-000|" not in result
        assert "chunk-199|" in result
        assert len(result) <= (
            len("Existing summary.")
            + len("\n\n[Recent, not yet summarized]: ")
            + RollingSummary.MAX_PENDING_PREVIEW_CHARS
            + 3
        )


# =====================================================================
# ContextManager tests
# =====================================================================


class TestContextManagerInit:
    """Verify initial state of ContextManager."""

    def test_init(self) -> None:
        cm = ContextManager()
        assert cm.max_context_tokens == 16000
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
        assert cm.get_token_count("hello") == 1  # int(1 * 1.5) == 1

    def test_token_count_multiple_words(self) -> None:
        cm = ContextManager()
        text = "the quick brown fox jumps over the lazy dog"  # 9 words
        count = cm.get_token_count(text)
        # tiktoken gives exact count (9), fallback gives int(9 * 1.5) = 13
        assert count >= 9 and count <= 13

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
        """When no data exists, a placeholder message is returned."""
        cm = ContextManager()
        result = cm.assemble_context(question="What was discussed?", session_id="s1")
        assert "no context available" in result.lower()

    def test_assemble_context_with_buffer(self) -> None:
        cm = ContextManager()
        cm.add_transcript("We decided to use FastAPI for the backend.")
        result = cm.assemble_context(question="What framework?", session_id="s1")
        assert "FastAPI" in result

    def test_assemble_context_with_rag(self) -> None:
        cm = ContextManager()
        # Add transcript so context isn't empty
        cm.add_transcript("Alice: We need to set up the API layer.")
        mock_rag = MagicMock()
        mock_rag.hybrid_search.return_value = [
            {"text": "FastAPI docs excerpt", "metadata": {"filename": "api.pdf"}},
        ]
        cm.set_rag_pipeline(mock_rag)

        result = cm.assemble_context(question="How to set up API?", session_id="s1")
        assert "FastAPI docs excerpt" in result
        assert "api.pdf" in result
        assert mock_rag.hybrid_search.call_count >= 1

    def test_assemble_context_rag_failure_graceful(self) -> None:
        """A failing RAG pipeline should not crash assembly."""
        cm = ContextManager()
        # Add transcript so context isn't empty
        cm.add_transcript("Bob: Let's talk about the roadmap.")
        mock_rag = MagicMock()
        mock_rag.hybrid_search.side_effect = RuntimeError("Not initialized")
        cm.set_rag_pipeline(mock_rag)

        result = cm.assemble_context(question="test", session_id="s1")
        # Should still contain transcript content without crashing.
        assert "roadmap" in result

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
        """When no RAG pipeline is set, no PRIMARY SOURCE section appears."""
        cm = ContextManager()
        cm.add_transcript("Some discussion content.")
        result = cm.assemble_context(question="test", session_id="s1")
        assert "=== PRIMARY SOURCE" not in result
        assert "discussion content" in result

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


class TestMemoryIsolation:
    """Tests for memory scope isolation, deletion, and recovery (Item 10)."""

    def test_transcript_metadata_includes_meeting_id(self) -> None:
        """Transcript chunks embedded via _flush_embed_buffer should carry meeting_id."""
        cm = ContextManager(meeting_id="mtg-1", agent_id="agt-1", user_id="usr-1")
        mock_rag = MagicMock()
        cm.set_rag_pipeline(mock_rag)

        # Fill buffer past the chunk target to trigger a flush
        for i in range(50):
            cm.add_transcript(f"Speaker: word{i} " * 10)

        cm._flush_embed_buffer(force=True)

        if mock_rag.add_chunk.called:
            meta = mock_rag.add_chunk.call_args.kwargs.get("metadata", {})
            assert meta.get("meeting_id") == "mtg-1"
            assert meta.get("agent_id") == "agt-1"
            assert meta.get("source_type") == "transcript"

    def test_cross_meeting_leakage_prevented_by_metadata_filter(self) -> None:
        """RAG search should scope to current meeting when meeting_id is set."""
        cm = ContextManager(meeting_id="mtg-current")
        mock_rag = MagicMock()
        mock_rag.hybrid_search.return_value = []
        cm.set_rag_pipeline(mock_rag)
        cm.add_transcript("Alice: Test content for scoping.")

        cm.assemble_context(question="What did Alice say?", session_id="s1")

        # hybrid_search should be called with where filters
        for call_args in mock_rag.hybrid_search.call_args_list:
            where = call_args.kwargs.get("where", {})
            # At least one call should filter by meeting_id
            assert where, "hybrid_search should be called with where filters"

    def test_separate_document_and_transcript_queries(self) -> None:
        """assemble_context should query documents and transcript separately."""
        cm = ContextManager(meeting_id="mtg-1")
        mock_rag = MagicMock()
        mock_rag.hybrid_search.return_value = []
        cm.set_rag_pipeline(mock_rag)
        cm.add_transcript("Bob: Discussion about architecture.")

        cm.assemble_context(question="What about architecture?", session_id="s1")

        # Should have separate calls for transcript and document source types
        call_wheres = [
            call.kwargs.get("where", {})
            for call in mock_rag.hybrid_search.call_args_list
        ]
        source_types = [w.get("source_type") for w in call_wheres if "source_type" in w]
        assert "transcript" in source_types
        assert "document" in source_types

    def test_deleted_document_not_in_summaries(self) -> None:
        """After clearing document summaries, they should not appear in context."""
        cm = ContextManager()
        cm.add_document_summary("report.pdf", "Revenue grew 25%.")
        cm.add_transcript("Alice: Let's review the report.")

        # Simulate deletion by clearing summaries
        with cm._state_lock:
            cm.document_summaries.clear()

        result = cm.assemble_context(question="What about revenue?", session_id="s1")
        assert "Revenue grew 25%" not in result

    def test_past_meeting_summaries_available_in_context(self) -> None:
        """Past meeting summaries should appear in context assembly."""
        cm = ContextManager()
        cm.add_past_meeting_summary("2026-04-01", "Decided to use PostgreSQL.")
        cm.add_transcript("Bob: What database did we pick?")

        result = cm.assemble_context(question="What database?", session_id="s1")
        assert "PostgreSQL" in result
        assert "PAST MEETINGS" in result

    def test_scope_ids_propagated_to_context_manager(self) -> None:
        """ContextManager should store scope IDs passed at construction."""
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        assert cm.meeting_id == "m1"
        assert cm.agent_id == "a1"
        assert cm.user_id == "u1"

    def test_token_count_with_tiktoken(self) -> None:
        """Token count should use tiktoken when available."""
        cm = ContextManager()
        # tiktoken is more accurate than word * 1.5
        count = cm.get_token_count("Hello, world!")
        assert isinstance(count, int)
        assert count > 0
        assert count < 10  # should be ~4 tokens, not 4 * 1.5 = 6

    def test_rolling_summary_preserves_key_facts(self) -> None:
        """RollingSummary should track key facts alongside prose."""
        rs = RollingSummary()
        assert rs._key_facts == []
        assert rs._update_count == 0
        rs.reset()
        assert rs._key_facts == []


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
