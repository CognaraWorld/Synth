import asyncio
import json as _json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.routes.auth import get_current_user
from app.models.database import Agent, ChatMessage, Meeting, MeetingSummary, User, get_db
from app.models.schemas import ChatHistoryResponse, ChatResponse, ChatSendRequest
from app.utils.bot_profiles import build_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

# Lazy LLM singleton — avoids import-time failure if LLM deps are missing.
_llm = None

# Per-user rate limit: max requests per minute.
_CHAT_RATE_LIMIT = 20
_rate_limit_buckets: dict[str, list[float]] = {}
_rate_limit_lock = asyncio.Lock()


def _get_llm():
    global _llm
    if _llm is None:
        from app.core.llm import LLMClient
        _llm = LLMClient()
    return _llm


async def _check_rate_limit(user_id: str) -> None:
    """Async-safe in-memory sliding window rate limiter."""
    now = datetime.now(timezone.utc).timestamp()
    window = 60.0  # 1 minute

    async with _rate_limit_lock:
        bucket = _rate_limit_buckets.get(user_id, [])
        bucket = [t for t in bucket if now - t < window]
        if len(bucket) >= _CHAT_RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Chat rate limit exceeded. Max {_CHAT_RATE_LIMIT} messages per minute.",
            )
        bucket.append(now)
        _rate_limit_buckets[user_id] = bucket


_CHAT_MODE_SUFFIX = (
    "\n\nYou are now in chat mode answering questions about this meeting. "
    "Use the transcript, summary, and documents to answer accurately. "
    "If you don't know, say so."
)


async def _get_meeting_or_raise(
    meeting_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Meeting:
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.agent).joinedload(Agent.documents))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if meeting.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return meeting


def _format_summary_field(value: str) -> str:
    """Deserialize JSON-encoded summary fields into readable bullet points."""
    try:
        items = _json.loads(value)
        if isinstance(items, list):
            return "\n".join(f"- {item}" for item in items)
    except (ValueError, TypeError):
        pass
    return value


async def _build_chat_context(meeting: Meeting, chat_history: list[ChatMessage], db: AsyncSession) -> str:
    parts: list[str] = []

    if meeting.transcript:
        transcript = meeting.transcript
        if len(transcript) > 12000:
            transcript = "...(earlier transcript omitted)...\n" + transcript[-12000:]
        parts.append(f"## Meeting Transcript\n{transcript}")
    else:
        parts.append("## Meeting Transcript\nNo transcript available yet.")

    summary_result = await db.execute(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
    )
    summary = summary_result.scalar_one_or_none()
    if summary:
        parts.append(f"## Meeting Summary\n{summary.content}")
        if summary.key_points:
            parts.append(f"## Key Points\n{_format_summary_field(summary.key_points)}")
        if summary.action_items:
            parts.append(f"## Action Items\n{_format_summary_field(summary.action_items)}")
        if summary.decisions:
            parts.append(f"## Decisions\n{_format_summary_field(summary.decisions)}")

    if meeting.agent and meeting.agent.documents:
        document_blocks = []
        for document in meeting.agent.documents:
            if document.doc_summary:
                document_blocks.append(f"{document.filename}: {document.doc_summary}")
        if document_blocks:
            parts.append("## Documents\n" + "\n\n".join(document_blocks[:5]))

    if chat_history:
        history_text = "\n".join(
            f"{'User' if message.role == 'user' else 'Assistant'}: {message.content}"
            for message in chat_history[-20:]
        )
        parts.append(f"## Previous Chat\n{history_text}")

    return "\n\n".join(parts)


@router.post("/meetings/{meeting_id}/chat", response_model=ChatResponse)
async def send_chat_message(
    meeting_id: UUID,
    req: ChatSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_rate_limit(str(current_user.id))

    meeting = await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    user_message = ChatMessage(
        meeting_id=meeting_id,
        user_id=current_user.id,
        role="user",
        content=req.message,
    )
    db.add(user_message)
    await db.flush()

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.meeting_id == meeting_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    chat_history = list(reversed(history_result.scalars().all()))
    context = await _build_chat_context(meeting=meeting, chat_history=chat_history, db=db)

    agent = meeting.agent
    system_prompt = (
        (agent.system_prompt if agent and agent.system_prompt else None)
        or build_system_prompt(
            getattr(agent, "mode", "general"),
            getattr(agent, "description", ""),
            getattr(agent, "persona_id", "general"),
        )
    )
    system_prompt = f"{system_prompt}{_CHAT_MODE_SUFFIX}"

    try:
        assistant_reply = await _get_llm().async_query(
            context=context,
            question=req.message,
            system_prompt=system_prompt,
        )
    except Exception:
        logger.exception("LLM query failed for meeting %s", meeting_id)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please try again.",
        )

    assistant_message = ChatMessage(
        meeting_id=meeting_id,
        user_id=current_user.id,
        role="assistant",
        content=assistant_reply,
    )
    db.add(assistant_message)
    await db.flush()
    await db.commit()

    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
    }


@router.get("/meetings/{meeting_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    meeting_id: UUID,
    per_page: int = Query(default=50, ge=1, le=100),
    before: datetime | None = Query(default=None, description="Load messages before this timestamp (for pagination)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest N messages in chronological order.

    Default behavior (no ``before``): fetch the most recent ``per_page``
    messages and return them oldest-first for rendering.

    With ``before``: fetch ``per_page`` messages older than the given
    timestamp (for infinite-scroll-up pagination).
    """
    await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    count_result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.meeting_id == meeting_id)
    )
    total = count_result.scalar() or 0

    query = (
        select(ChatMessage)
        .where(ChatMessage.meeting_id == meeting_id)
    )

    if before is not None:
        # Normalize to naive UTC — DB stores naive UTC timestamps.
        if before.tzinfo is not None:
            before = before.astimezone(timezone.utc).replace(tzinfo=None)
        query = query.where(ChatMessage.created_at < before)

    # Fetch newest N by ordering DESC then reverse for chronological render.
    query = query.order_by(ChatMessage.created_at.desc()).limit(per_page)
    result = await db.execute(query)
    messages = list(reversed(result.scalars().all()))

    return ChatHistoryResponse(
        messages=messages,
        meeting_id=meeting_id,
        total=total,
    )
