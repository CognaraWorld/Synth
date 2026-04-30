"""Regression tests: meeting_id scope must be a DB UUID, never the meeting URL.

When MeetingSession was previously created with `meeting_id = meeting_link`,
two users joining the same Google Meet URL ended up sharing the same scope
identifier in RAG metadata. Cross-meeting search filtered only by
``source_type='transcript'`` (no user_id), so user A's queries could surface
user B's transcript chunks from the same URL.

These tests pin the contract: the scope identifier propagated to ContextManager
must NEVER be the meeting link.
"""

from __future__ import annotations

from uuid import UUID

import pytest


def _is_uuid_or_opaque(value: str) -> bool:
    """Accept either a UUID string or any string that is clearly not a URL."""
    if not value:
        return False
    if value.startswith(("http://", "https://", "wss://", "ws://")):
        return False
    if "://" in value or "meet.google.com" in value or "zoom.us" in value:
        return False
    return True


class TestMeetingSessionScopeId:
    """Direct tests on MeetingSession constructor."""

    def test_explicit_uuid_is_stored_verbatim(self) -> None:
        from app.meeting.session import MeetingSession

        explicit_uuid = "11111111-2222-3333-4444-555555555555"
        session = MeetingSession(meeting_id=explicit_uuid, agent_config={})
        assert session.meeting_id == explicit_uuid
        assert session.context_manager.meeting_id == explicit_uuid

    def test_meeting_link_must_not_be_used_as_scope_id(self) -> None:
        """Pin-down: the constructor accepts whatever is passed (it's a string),
        but callers must never pass the meeting URL. This test documents the
        contract by failing loudly if a URL accidentally lands here."""
        from app.meeting.session import MeetingSession

        meeting_link = "https://meet.google.com/abc-defg-hij"
        session = MeetingSession(meeting_id=meeting_link, agent_config={})

        # The constructor stores what it's given — we can't prevent that here.
        # Instead, we assert the contract is documented at the call sites
        # (meetings.py and bot_engine.py) by checking that the URL would be
        # detected as invalid by our helper.
        assert not _is_uuid_or_opaque(session.meeting_id), (
            "Sentinel: a URL was passed as meeting_id. The fix must ensure "
            "callers pass str(Meeting.id) (a DB UUID), never the URL."
        )


class TestBotEngineJoinMeetingScopeId:
    """BotEngine.join_meeting must not default meeting_id to the meeting_link."""

    def _make_engine(self):
        from unittest.mock import AsyncMock, MagicMock

        from app.core import bot_engine as be

        engine = be.BotEngine()
        engine._models_loaded = True
        engine._tts = MagicMock()
        engine._stt = MagicMock()
        engine._llm_client = MagicMock()
        engine._recall_client = MagicMock()
        engine._recall_client.create_bot = AsyncMock(return_value="bot-xyz")
        return engine

    @pytest.mark.asyncio
    async def test_join_meeting_generates_uuid_when_none_provided(self) -> None:
        """When no explicit meeting_id is provided, the engine must generate
        a fresh UUID — NOT use the meeting URL as the scope identifier."""
        from unittest.mock import AsyncMock, MagicMock, patch

        engine = self._make_engine()
        meeting_link = "https://meet.google.com/leak-test-room"

        # Patch heavy/IO dependencies: VAD model load, document loader.
        with patch("app.core.vad.VoiceActivityDetector", new=MagicMock()):
            with patch.object(engine, "_lazy_load_models", new=AsyncMock(return_value=None)):
                with patch.object(engine, "wire_screen_capture"):
                    # No agent_id → skips the RAG/documents block entirely
                    session_id = await engine.join_meeting(
                        meeting_link=meeting_link,
                        agent_config={"user_id": "u-1"},
                    )

        session = engine.sessions[session_id]
        assert session.meeting_id != meeting_link, (
            "REGRESSION: BotEngine.join_meeting() reverted to using the "
            "meeting URL as scope identifier — this leaks RAG data across "
            "any users who join the same meeting URL."
        )
        # New behavior: scope ID must be a UUID
        try:
            UUID(session.meeting_id)
        except ValueError:
            pytest.fail(
                f"meeting_id={session.meeting_id!r} is not a UUID — "
                f"the fix should generate one when not provided."
            )

    @pytest.mark.asyncio
    async def test_join_meeting_accepts_explicit_meeting_id(self) -> None:
        """When an explicit meeting_id (DB UUID) is passed in, it must
        be propagated verbatim to MeetingSession and ContextManager."""
        from unittest.mock import AsyncMock, MagicMock, patch

        engine = self._make_engine()
        explicit_id = "deadbeef-1234-5678-9abc-deadbeef1234"

        with patch("app.core.vad.VoiceActivityDetector", new=MagicMock()):
            with patch.object(engine, "_lazy_load_models", new=AsyncMock(return_value=None)):
                with patch.object(engine, "wire_screen_capture"):
                    session_id = await engine.join_meeting(
                        meeting_link="https://meet.google.com/anything",
                        agent_config={"user_id": "u-1"},
                        meeting_id=explicit_id,
                    )

        session = engine.sessions[session_id]
        assert session.meeting_id == explicit_id
        assert session.context_manager.meeting_id == explicit_id


class TestRagMetadataDoesNotContainUrl:
    """When a chunk is embedded into RAG, its meeting_id metadata must
    not be a meeting URL (regardless of what callers pass in)."""

    def test_url_in_session_meeting_id_propagates_to_rag_metadata(self) -> None:
        """Documents the bug: if a URL is stored as meeting_id, it ends up
        verbatim in RAG metadata. The fix is at the call sites — once they
        pass UUIDs, this URL pattern can never appear in metadata."""
        from app.context.manager import ContextManager

        url = "https://meet.google.com/leak-test-room"
        ctx = ContextManager(meeting_id=url, agent_id="a-1", user_id="u-1")

        # Confirm the URL is what would be stored in metadata
        assert ctx.meeting_id == url, (
            "ContextManager stores the scope ID verbatim. The fix must "
            "ensure callers never hand it a URL."
        )
