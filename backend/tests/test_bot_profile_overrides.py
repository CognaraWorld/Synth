"""Tests for dashboard bot profile and per-meeting override support."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.schemas import BotProfileUpsert, MeetingCreate, MeetingOverrideUpsert


class TestAgentPrimaryBehavior:
    @pytest.mark.asyncio
    async def test_create_agent_marks_first_agent_as_primary(self) -> None:
        from app.api.routes.agents import create_agent

        current_user = MagicMock(id=uuid4())
        primary_result = MagicMock()
        primary_result.scalar.return_value = 0  # count check: 0 agents (< 10)
        primary_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = primary_result
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await create_agent(
            agent_data=MagicMock(
                name="Synth",
                description="Helpful meeting assistant",
                mode="general",
                persona_id="general",
                voice="female",
                response_mode="name_only",
            ),
            current_user=current_user,
            db=db,
        )

        created_agent = db.add.call_args.args[0]
        assert created_agent.is_primary is True
        assert created_agent.voice == "female"
        assert created_agent.response_mode == "name_only"

    @pytest.mark.asyncio
    async def test_create_agent_repairs_duplicate_primaries_before_inserting(self) -> None:
        from app.api.routes.agents import create_agent

        current_user = MagicMock(id=uuid4())
        primary_a = MagicMock(id=uuid4(), is_primary=True)
        primary_b = MagicMock(id=uuid4(), is_primary=True)

        primary_result = MagicMock()
        primary_result.scalar.return_value = 0  # count check: 0 agents (< 10)
        primary_result.scalars.return_value.all.return_value = [primary_a, primary_b]

        db = AsyncMock()
        db.execute.return_value = primary_result
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await create_agent(
            agent_data=MagicMock(
                name="Synth",
                description="Helpful meeting assistant",
                mode="general",
                persona_id="general",
                voice="female",
                response_mode="name_only",
            ),
            current_user=current_user,
            db=db,
        )

        created_agent = db.add.call_args.args[0]
        assert primary_a.is_primary is True
        assert primary_b.is_primary is False
        assert created_agent.is_primary is False

    @pytest.mark.asyncio
    async def test_create_agent_uses_fixed_voice_for_persona(self) -> None:
        from app.api.routes.agents import create_agent

        current_user = MagicMock(id=uuid4())
        primary_result = MagicMock()
        primary_result.scalar.return_value = 0  # count check: 0 agents (< 10)
        primary_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = primary_result
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await create_agent(
            agent_data=MagicMock(
                name="Synth",
                description="Helpful meeting assistant",
                mode="general",
                persona_id="strategist",
                voice="female",
                response_mode="name_only",
            ),
            current_user=current_user,
            db=db,
        )

        created_agent = db.add.call_args.args[0]
        assert created_agent.persona_id == "strategist"
        assert created_agent.mode == "general"
        assert created_agent.voice == "male"

    @pytest.mark.asyncio
    async def test_delete_primary_agent_reassigns_new_primary(self) -> None:
        from app.api.routes.agents import delete_agent

        current_user = MagicMock(id=uuid4())
        deleted_agent = MagicMock(id=uuid4(), is_primary=True)
        replacement_agent = MagicMock(id=uuid4(), is_primary=False)

        # 1st: agent lookup
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = deleted_agent
        # 2nd: document list for cleanup (empty — no docs)
        doc_result = MagicMock()
        doc_result.scalars.return_value.all.return_value = []
        # 3rd: replacement agent lookup
        replacement_result = MagicMock()
        replacement_result.scalars.return_value.first.return_value = replacement_agent
        # 4th: mark_primary_agent query
        mark_result = MagicMock()
        mark_result.scalars.return_value.all.return_value = [replacement_agent]

        db = AsyncMock()
        db.execute.side_effect = [agent_result, doc_result, replacement_result, mark_result]
        db.delete = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        with patch("app.api.routes.documents._get_rag_pipeline", return_value=None):
            await delete_agent(
                agent_id=deleted_agent.id,
                current_user=current_user,
                db=db,
            )

        assert replacement_agent.is_primary is True

    @pytest.mark.asyncio
    async def test_update_agent_drops_none_fields_from_payload(self) -> None:
        from app.api.routes.agents import update_agent
        from app.models.schemas import AgentUpdate

        current_user = MagicMock(id=uuid4())
        agent = MagicMock(
            id=uuid4(),
            name="Synth",
            description="Existing description",
            mode="general",
            voice="female",
            response_mode="name_only",
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = agent

        db = AsyncMock()
        db.execute.return_value = result
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await update_agent(
            agent_id=agent.id,
            update_data=AgentUpdate(voice=None, description="Updated"),
            current_user=current_user,
            db=db,
        )

        assert agent.voice == "female"
        assert agent.description == "Updated"


class TestBotProfileRoutes:
    @pytest.mark.asyncio
    async def test_get_bot_profile_uses_existing_agent_when_no_primary_flag_exists(self) -> None:
        from app.api.routes.bot import get_bot_profile

        current_user = MagicMock(id=uuid4())
        fallback_agent = MagicMock(id=uuid4(), is_primary=False, name="Fallback")

        primary_result = MagicMock()
        primary_result.scalars.return_value.all.return_value = [fallback_agent]

        db = AsyncMock()
        db.execute.return_value = primary_result

        result = await get_bot_profile(current_user=current_user, db=db)
        assert result is fallback_agent

    @pytest.mark.asyncio
    async def test_upsert_bot_profile_creates_primary_agent(self) -> None:
        from app.api.routes.bot import upsert_bot_profile

        current_user = MagicMock(id=uuid4())
        primary_result = MagicMock()
        primary_result.scalars.return_value.all.return_value = []
        mark_result = MagicMock()
        mark_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.side_effect = [primary_result, mark_result]
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        async def flush_side_effect() -> None:
            created_agent = db.add.call_args.args[0]
            created_agent.id = uuid4()
            created_agent.created_at = datetime.now(timezone.utc)
            created_agent.updated_at = created_agent.created_at

        db.flush.side_effect = flush_side_effect

        result = await upsert_bot_profile(
            profile_data=BotProfileUpsert(
                name="Synth",
                description="Technical meeting copilot",
                mode="general",
                persona_id="strategist",
                voice="female",
                response_mode="proactive",
            ),
            current_user=current_user,
            db=db,
        )

        created_agent = db.add.call_args.args[0]
        assert created_agent.is_primary is True
        assert created_agent.voice == "female"
        assert created_agent.mode == "general"
        assert created_agent.persona_id == "strategist"
        assert created_agent.response_mode == "proactive"
        assert "Technical meeting copilot" in created_agent.system_prompt
        assert result is created_agent


class TestMeetingOverrides:
    @pytest.mark.asyncio
    async def test_create_meeting_uses_primary_agent_when_agent_id_missing(self) -> None:
        from app.api.routes.meetings import create_meeting

        current_user = MagicMock(id=uuid4(), credits=60)
        primary_agent = MagicMock(id=uuid4(), is_primary=True)

        # 1st execute: active meetings count check (< 20)
        active_count_result = MagicMock()
        active_count_result.scalar.return_value = 0
        # 2nd execute: atomic reserve (rowcount=1)
        reserve_result = MagicMock(rowcount=1)
        # 3rd execute: get_effective_primary_agent -> select agents by user
        agent_result = MagicMock()
        agent_result.scalars.return_value.all.return_value = [primary_agent]

        db = AsyncMock()
        db.execute.side_effect = [active_count_result, reserve_result, agent_result]
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_settings = MagicMock(recall_api_key="", deepgram_api_key="")
        with (
            patch("app.api.routes.meetings.detect_platform", return_value="zoom"),
            patch("app.api.routes.meetings.get_settings", return_value=mock_settings),
        ):
            meeting = await create_meeting(
                meeting_data=MeetingCreate(meeting_link="https://zoom.us/j/123456789"),
                current_user=current_user,
                db=db,
            )

        created_meeting = db.add.call_args.args[0]
        assert created_meeting.agent_id == primary_agent.id

    @pytest.mark.asyncio
    async def test_create_meeting_with_unknown_explicit_agent_keeps_agent_not_found_message(self) -> None:
        from app.api.routes.meetings import create_meeting

        current_user = MagicMock(id=uuid4(), credits=3)
        # active meetings count (first call)
        active_count_result = MagicMock()
        active_count_result.scalar.return_value = 0
        # reserve credits (second call, rowcount=1)
        reserve_result = MagicMock(rowcount=1)
        # agent lookup (third call, returns None -> 404)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute.side_effect = [active_count_result, reserve_result, query_result]

        with pytest.raises(HTTPException, match="Agent not found"):
            await create_meeting(
                meeting_data=MeetingCreate(
                    agent_id=uuid4(),
                    meeting_link="https://zoom.us/j/123456789",
                ),
                current_user=current_user,
                db=db,
            )

    @pytest.mark.asyncio
    async def test_upsert_meeting_override_rejects_active_meeting(self) -> None:
        from app.api.routes.meetings import upsert_meeting_override

        meeting = MagicMock(status="active", override=None)
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting

        db = AsyncMock()
        db.execute.return_value = result

        with pytest.raises(HTTPException, match="before the meeting is active"):
            await upsert_meeting_override(
                meeting_id=uuid4(),
                override_data=MeetingOverrideUpsert(description="Test override"),
                current_user=MagicMock(id=uuid4()),
                db=db,
            )

    @pytest.mark.asyncio
    async def test_upsert_meeting_override_builds_prompt_from_description(self) -> None:
        from app.api.routes.meetings import upsert_meeting_override

        meeting = MagicMock(
            id=uuid4(),
            status="pending",
            override=None,
            agent=MagicMock(mode="general", persona_id="general", description="Helpful assistant"),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting

        db = AsyncMock()
        db.execute.return_value = result
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        async def refresh_side_effect(override) -> None:
            override.id = uuid4()
            override.created_at = datetime.now(timezone.utc)
            override.updated_at = override.created_at

        db.refresh.side_effect = refresh_side_effect

        override = await upsert_meeting_override(
            meeting_id=meeting.id,
            override_data=MeetingOverrideUpsert(
                description="Answer like a concise finance analyst",
            ),
            current_user=MagicMock(id=uuid4()),
            db=db,
        )

        created_override = db.add.call_args.args[0]
        assert created_override.mode == "general"
        assert created_override.persona_id == "general"
        assert "concise finance analyst" in created_override.system_prompt
        assert override is created_override


class TestMeetingOverrideSchema:
    def test_override_requires_at_least_one_field(self) -> None:
        with pytest.raises(ValueError, match="At least one override field"):
            MeetingOverrideUpsert()
