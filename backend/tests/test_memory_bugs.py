"""Tests for memory system bug fixes.

Covers: user_id scope isolation, embed retry journal, truncation direction,
and checkpoint save/restore.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.context.manager import ContextManager


class TestPastMeetingScopeIsolation:
    """Fix: past meeting query must filter by user_id."""

    def test_context_manager_stores_user_id(self) -> None:
        user_id = str(uuid4())
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id=user_id)
        assert cm.user_id == user_id

    def test_past_meeting_summary_added_correctly(self) -> None:
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        cm.add_past_meeting_summary("2026-04-01", "Discussed pricing strategy")
        assert len(cm.past_meeting_summaries) == 1
        assert cm.past_meeting_summaries[0]["summary"] == "Discussed pricing strategy"


class TestEmbedFailureRetry:
    """Fix: failed embed chunks are journaled and retried."""

    def test_failed_embed_is_journaled(self) -> None:
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        mock_rag = MagicMock()
        mock_rag.add_chunk.side_effect = RuntimeError("ChromaDB connection lost")
        cm.set_rag_pipeline(mock_rag)

        # Simulate evicted transcript entering embed buffer
        now = datetime.now(timezone.utc)
        cm._transcript_embed_buffer = [(now, "Alice: We should use PostgreSQL for the main DB")]
        cm._flush_embed_buffer(force=True)

        # The failed chunk should be in the retry journal
        assert len(cm._embed_failed_chunks) == 1
        assert "PostgreSQL" in cm._embed_failed_chunks[0][0]

    def test_failed_embed_retried_on_next_flush(self) -> None:
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        mock_rag = MagicMock()

        # Always fail
        mock_rag.add_chunk.side_effect = RuntimeError("ChromaDB down")
        cm.set_rag_pipeline(mock_rag)

        now = datetime.now(timezone.utc)
        cm._transcript_embed_buffer = [(now, "Bob: The deadline is Friday")]
        cm._flush_embed_buffer(force=True)
        assert len(cm._embed_failed_chunks) == 1

        # Now make RAG work again — retry on next flush should succeed
        mock_rag.add_chunk.side_effect = None
        cm._flush_embed_buffer(force=True)
        assert len(cm._embed_failed_chunks) == 0

    def test_failed_chunks_dropped_after_3_retries(self) -> None:
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        mock_rag = MagicMock()
        mock_rag.add_chunk.side_effect = RuntimeError("Permanently broken")
        cm.set_rag_pipeline(mock_rag)

        # Manually add a failed chunk
        cm._embed_failed_chunks = [("some text", {"meeting_id": "m1"})]

        # Retry 3 times
        for _ in range(3):
            cm._transcript_embed_buffer = []
            cm._flush_embed_buffer(force=True)

        # After 3 retries, chunks should be dropped
        assert len(cm._embed_failed_chunks) == 0


class TestTruncationDirection:
    """Fix: RAG/doc truncation keeps the beginning, buffer keeps the end."""

    def test_truncate_from_end_keeps_beginning(self) -> None:
        cm = ContextManager()
        text = "Key decision: Use PostgreSQL. " + "Details about implementation. " * 50
        result = cm._truncate_from_end(text, 20)
        assert result.startswith("Key decision")
        assert result.endswith("...")

    def test_truncate_from_beginning_keeps_end(self) -> None:
        cm = ContextManager()
        text = "Old irrelevant context. " * 50 + "Recent important discussion."
        result = cm._truncate_from_beginning(text, 20)
        assert "Recent important discussion" in result

    def test_truncate_from_end_returns_full_text_if_within_budget(self) -> None:
        cm = ContextManager()
        text = "Short text"
        result = cm._truncate_from_end(text, 1000)
        assert result == text

    def test_truncate_from_end_returns_empty_on_zero_budget(self) -> None:
        cm = ContextManager()
        text = "Some text that won't fit"
        result = cm._truncate_from_end(text, 0)
        assert result == ""


class TestCheckpointSaveRestore:
    """Fix: memory state can be checkpointed and restored for crash recovery."""

    def test_get_checkpoint_state_captures_all_layers(self) -> None:
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        cm.rolling_summary.summary = "Team discussed Q4 roadmap"
        cm.rolling_summary._key_facts = ["Shipping date: Dec 15"]
        cm._entities["decisions"].add("Use PostgreSQL")
        cm._entities["people"].add("Alice")

        checkpoint = cm.get_checkpoint_state()

        assert checkpoint["meeting_id"] == "m1"
        assert checkpoint["rolling_summary"] == "Team discussed Q4 roadmap"
        assert "Shipping date: Dec 15" in checkpoint["key_facts"]
        assert "Use PostgreSQL" in checkpoint["entities"]["decisions"]
        assert "Alice" in checkpoint["entities"]["people"]

    def test_restore_from_checkpoint_recovers_state(self) -> None:
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        checkpoint = {
            "rolling_summary": "Discussed pricing and hiring",
            "key_facts": ["Price: $99/mo", "Hire 3 engineers"],
            "entities": {
                "people": ["Alice", "Bob"],
                "decisions": ["Use PostgreSQL"],
                "topics": ["pricing"],
                "action_items": ["Draft proposal"],
            },
            "recent_transcript": "",
            "meeting_id": "m1",
        }

        cm.restore_from_checkpoint(checkpoint)

        assert cm.rolling_summary.summary == "Discussed pricing and hiring"
        assert cm.rolling_summary._key_facts == ["Price: $99/mo", "Hire 3 engineers"]
        assert "Alice" in cm._entities["people"]
        assert "Use PostgreSQL" in cm._entities["decisions"]
        assert "Draft proposal" in cm._entities["action_items"]

    def test_restore_from_empty_checkpoint_is_noop(self) -> None:
        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        cm.rolling_summary.summary = "Existing summary"

        cm.restore_from_checkpoint({})
        assert cm.rolling_summary.summary == "Existing summary"

        cm.restore_from_checkpoint(None)
        assert cm.rolling_summary.summary == "Existing summary"

    def test_checkpoint_roundtrip_via_json(self) -> None:
        import json

        cm = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        cm.rolling_summary.summary = "Q4 roadmap finalized"
        cm.rolling_summary._key_facts = ["Launch Dec 15"]
        cm._entities["people"].add("Alice")

        checkpoint = cm.get_checkpoint_state()
        serialized = json.dumps(checkpoint, default=str)
        deserialized = json.loads(serialized)

        cm2 = ContextManager(meeting_id="m1", agent_id="a1", user_id="u1")
        cm2.restore_from_checkpoint(deserialized)

        assert cm2.rolling_summary.summary == "Q4 roadmap finalized"
        assert "Alice" in cm2._entities["people"]
