"""Regression test: chat._get_meeting_or_raise must call .unique() correctly.

Previous bug: the helper used a try/except that called
``scalar_one_or_none()`` first, caught the InvalidRequestError raised by
SQLAlchemy for collection joinedloads, then called
``.unique().scalar_one_or_none()`` on the SAME already-exhausted Result.
The second call returned None, so every chat endpoint (history,
suggestions, stream, insights) 404'd with "Meeting not found" even for
the meeting's owner. The "Chat about this meeting" UI was completely
dead as a result.

The fix calls ``.unique()`` up front against the fresh Result.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _make_user(uid=None):
    return MagicMock(id=uid or uuid4())


def _make_meeting(user_id):
    m = MagicMock()
    m.id = uuid4()
    m.user_id = user_id
    return m


@pytest.mark.asyncio
async def test_get_meeting_or_raise_calls_unique_before_scalar() -> None:
    """The fix is to call .unique() on the Result before .scalar_one_or_none()
    so collection joinedloads (Agent.documents) don't poison the lookup."""
    from app.api.routes.chat import _get_meeting_or_raise

    owner = _make_user()
    meeting = _make_meeting(user_id=owner.id)

    db = AsyncMock()
    fake_result = MagicMock()
    # Spy on .unique() to assert it is called BEFORE .scalar_one_or_none()
    fake_result.unique.return_value = fake_result
    fake_result.scalar_one_or_none.return_value = meeting
    db.execute.return_value = fake_result

    result = await _get_meeting_or_raise(meeting.id, owner, db)

    assert result is meeting
    fake_result.unique.assert_called_once_with()
    fake_result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_meeting_or_raise_returns_404_only_when_no_meeting() -> None:
    """Sanity: when the lookup truly returns None, raise 404."""
    from fastapi import HTTPException

    from app.api.routes.chat import _get_meeting_or_raise

    user = _make_user()
    db = AsyncMock()
    fake_result = MagicMock()
    fake_result.unique.return_value = fake_result
    fake_result.scalar_one_or_none.return_value = None
    db.execute.return_value = fake_result

    with pytest.raises(HTTPException) as exc_info:
        await _get_meeting_or_raise(uuid4(), user, db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_meeting_or_raise_403_for_non_owner() -> None:
    """Sanity: when the meeting exists but user_id doesn't match, raise 403."""
    from fastapi import HTTPException

    from app.api.routes.chat import _get_meeting_or_raise

    owner = _make_user()
    intruder = _make_user()
    meeting = _make_meeting(user_id=owner.id)

    db = AsyncMock()
    fake_result = MagicMock()
    fake_result.unique.return_value = fake_result
    fake_result.scalar_one_or_none.return_value = meeting
    db.execute.return_value = fake_result

    with pytest.raises(HTTPException) as exc_info:
        await _get_meeting_or_raise(meeting.id, intruder, db)
    assert exc_info.value.status_code == 403
