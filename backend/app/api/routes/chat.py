import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.routes.auth import get_current_user
from app.core.llm import LLMClient
from app.models.database import Agent, ChatMessage, Meeting, MeetingSummary, User, get_db
from app.models.schemas import ChatHistoryResponse, ChatResponse, ChatSendRequest
from app.utils.bot_profiles import build_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])
_llm = LLMClient()

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
            parts.append(f"## Key Points\n{summary.key_points}")
        if summary.action_items:
            parts.append(f"## Action Items\n{summary.action_items}")
        if summary.decisions:
            parts.append(f"## Decisions\n{summary.decisions}")

    if meeting.agent and meeting.agent.documents:
        document_blocks = []
        for document in meeting.agent.documents:
            if document.doc_summary:
                document_blocks.append(f"{document.filename}: {document.doc_summary}")
        if document_blocks:
            parts.append(f"## Documents\n" + "\n\n".join(document_blocks[:5]))

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
        assistant_reply = await _llm.async_query(
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
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    offset = (page - 1) * per_page

    count_result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.meeting_id == meeting_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.meeting_id == meeting_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(per_page)
    )
    messages = result.scalars().all()

    return ChatHistoryResponse(
        messages=list(messages),
        meeting_id=meeting_id,
        total=total,
        page=page,
        per_page=per_page,
    )
