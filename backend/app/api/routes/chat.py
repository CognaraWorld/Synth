from __future__ import annotations

import asyncio
import json as _json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.responses import PlainTextResponse, StreamingResponse

from app.api.routes.auth import get_current_user
from app.core.chat_tools import CHAT_TOOLS, execute_tool
from app.core.insight_publisher import subscribe as subscribe_insights
from app.core.llm import LLMClient
from app.core.rate_limiter import _CHAT_RATE_LIMIT as _CORE_CHAT_RATE_LIMIT, get_rate_limiter
from app.models.database import Agent, ChatMessage, Meeting, MeetingSummary, User, get_db
from app.models.schemas import ChatHistoryResponse, ChatMessageResponse, ChatResponse, ChatSendRequest, CrossMeetingChatRequest
from app.utils.bot_profiles import build_system_prompt
from app.utils.query_router import classify_chat_complexity
from app.utils.suggestion_generator import generate_suggestions, get_cached_suggestions, cache_suggestions

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

_CHAT_MODE_SUFFIX = (
    "\n\nYou are now in chat mode answering questions about this meeting. "
    "Use the transcript, summary, and documents to answer accurately. "
    "If you don't know, say so.\n\n"
    "When referencing specific information from the transcript or documents, "
    "cite your source inline using these formats:\n"
    "- For transcript references: [T:MM:SS] immediately after the claim\n"
    "- For document references: [D:filename:page] immediately after the claim\n"
    "Only cite when you have a specific source. Do not fabricate citations."
)
_llm_client: LLMClient | None = None
_rag_pipeline = None
_TRANSCRIPT_CITATION_RE = re.compile(r"\[T:(\d{1,3}:\d{2})\]")
_DOCUMENT_CITATION_RE = re.compile(r"\[D:([^:\]]+):(\d+)\]")
_CHAT_RATE_LIMIT = _CORE_CHAT_RATE_LIMIT
_rate_limit_buckets = getattr(get_rate_limiter(), "_buckets", {})


def _get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def _get_rag():
    global _rag_pipeline
    if _rag_pipeline is None:
        from app.context.rag import RAGPipeline

        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def _format_summary_field(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(f"- {str(item).strip()}" for item in value if str(item).strip())
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        if stripped.startswith("["):
            try:
                parsed = _json.loads(stripped)
            except Exception:
                return stripped
            if isinstance(parsed, list):
                return "\n".join(f"- {str(item).strip()}" for item in parsed if str(item).strip())
        return stripped
    return str(value)


def _parse_citations(text: str) -> list[dict]:
    """Extract citation references from LLM response text."""
    citations = []
    for match in _TRANSCRIPT_CITATION_RE.finditer(text):
        citations.append(
            {
                "type": "transcript",
                "timestamp": match.group(1),
                "raw": match.group(0),
            }
        )
    for match in _DOCUMENT_CITATION_RE.finditer(text):
        citations.append(
            {
                "type": "document",
                "filename": match.group(1).strip(),
                "page": int(match.group(2)),
                "raw": match.group(0),
            }
        )
    return citations


def _should_use_tools(question: str) -> bool:
    """Detect if a question would benefit from tool use."""
    q = question.lower()
    tool_signals = [
        "search for",
        "search the web",
        "look up",
        "find out",
        "what is the latest",
        "current price",
        "current status",
        "current value",
        "today's news",
        "today's date",
        "recent news",
        "check if",
        "in the document",
        "in the file",
        "the pdf says",
        "create an action item",
        "add a task",
        "assign to",
        "create a todo",
    ]
    return any(signal in q for signal in tool_signals)


def _enrich_message_response(msg: ChatMessage) -> dict:
    """Convert ChatMessage to response dict with parsed metadata."""
    result = {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at,
        "citations": None,
        "tool_calls": None,
    }
    if msg.message_metadata:
        try:
            meta = _json.loads(msg.message_metadata)
            result["citations"] = meta.get("citations")
            result["tool_calls"] = meta.get("tool_calls")
        except Exception as exc:
            # Citations will silently disappear if this fires repeatedly
            # for valid messages — surface it at debug level so we can tell
            # corrupt-data cases apart from "message has no metadata".
            logger.debug(
                "Failed to parse message_metadata for msg %s: %s",
                getattr(msg, "id", "?"),
                exc,
            )
    elif msg.role == "assistant":
        citations = _parse_citations(msg.content)
        if citations:
            result["citations"] = citations
    return result


def _message_response_model(msg: ChatMessage) -> ChatMessageResponse:
    """Build a response model even when tests use non-persisted message objects."""
    created_at = msg.created_at or datetime.now(timezone.utc)
    return ChatMessageResponse(
        id=msg.id or uuid4(),
        role=msg.role,
        content=msg.content,
        created_at=created_at,
    )


async def _generate_follow_ups(response_text: str) -> list[str]:
    follow_ups: list[str] = []
    try:
        follow_ups_result = await generate_suggestions(
            summary_content=response_text[:500],
            transcript_tail=None,
            llm_query_fn=_get_llm().async_query,
        )
        follow_ups = follow_ups_result[:3]
    except Exception:
        logger.warning("Follow-up generation failed", exc_info=True)
    return follow_ups


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
    try:
        meeting = result.scalar_one_or_none()
    except InvalidRequestError:
        meeting = result.unique().scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if meeting.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return meeting


async def _check_rate_limit(user_id: str) -> None:
    """Compatibility wrapper for route code and existing tests."""
    limiter = get_rate_limiter()
    await limiter.check(user_id)


def _build_system_prompt_for_meeting(meeting: Meeting) -> str:
    agent = meeting.agent
    base_prompt = (
        (agent.system_prompt if agent and agent.system_prompt else None)
        or build_system_prompt(
            getattr(agent, "mode", "general"),
            getattr(agent, "description", ""),
            getattr(agent, "persona_id", "general"),
        )
    )
    return f"{base_prompt}{_CHAT_MODE_SUFFIX}"


async def _get_recent_chat_history(meeting_id: UUID, db: AsyncSession) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.meeting_id == meeting_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    return list(reversed(result.scalars().all()))


async def _build_chat_context(
    meeting: Meeting,
    chat_history: list[ChatMessage],
    db: AsyncSession,
    user_question: str = "",
) -> str:
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
        document_parts = []
        for document in meeting.agent.documents:
            if document.doc_summary:
                document_parts.append(f"{document.filename}: {document.doc_summary}")
        if document_parts:
            parts.append("## Documents\n" + "\n\n".join(document_parts[:5]))

    if user_question:
        try:
            rag = _get_rag()
            meeting_id_str = str(meeting.id)
            agent_id = str(meeting.agent_id) if meeting.agent_id else None
            transcript_chunks = rag.hybrid_search(
                query=user_question,
                top_k=5,
                where={
                    "$and": [
                        {"meeting_id": meeting_id_str},
                        {"source_type": "transcript"},
                    ]
                },
            )

            doc_chunks: list[dict] = []
            if meeting.agent and agent_id:
                doc_chunks = rag.hybrid_search(
                    query=user_question,
                    top_k=3,
                    where={
                        "$and": [
                            {"source_type": "document"},
                            {"agent_id": agent_id},
                        ]
                    },
                )

            if transcript_chunks or doc_chunks:
                passage_lines: list[str] = []
                for chunk in transcript_chunks[:5]:
                    meta = chunk.get("metadata", {})
                    speaker = meta.get("speaker", "Unknown")
                    timestamp = meta.get("start_time", "")
                    prefix = f"[Speaker: {speaker}, {timestamp}]" if timestamp else f"[Speaker: {speaker}]"
                    passage_lines.append(f"{prefix} {chunk['text']}")
                for chunk in doc_chunks[:3]:
                    meta = chunk.get("metadata", {})
                    filename = meta.get("filename", "document")
                    page = meta.get("page_number", "")
                    prefix = f"[Doc: {filename}, p.{page}]" if page else f"[Doc: {filename}]"
                    passage_lines.append(f"{prefix} {chunk['text']}")
                if passage_lines:
                    parts.append("## Relevant Passages\n" + "\n\n".join(passage_lines))
        except Exception:
            logger.warning("RAG search failed for chat context, continuing without", exc_info=True)

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

    chat_history = await _get_recent_chat_history(meeting_id=meeting_id, db=db)
    context = await _build_chat_context(
        meeting=meeting,
        chat_history=chat_history,
        db=db,
        user_question=req.message,
    )
    system_prompt = _build_system_prompt_for_meeting(meeting)
    complexity = classify_chat_complexity(req.message)
    tool_calls: list[dict] = []
    use_tools = _should_use_tools(req.message)

    search_client = None
    try:
        if use_tools:
            from app.core.search import SearchClient

            search_client = SearchClient()

            async def _exec_tool(name: str, inp: dict) -> str:
                return await execute_tool(
                    name,
                    inp,
                    search_client=search_client,
                    rag_pipeline=_get_rag(),
                    db=db,
                    meeting_id=meeting_id,
                )

            assistant_reply, tool_calls = await _get_llm().tool_use_query(
                context=context,
                question=req.message,
                system_prompt=system_prompt,
                tools=CHAT_TOOLS,
                tool_executor=_exec_tool,
            )
        elif complexity == "complex" and chat_history:
            history_dicts = [{"role": message.role, "content": message.content} for message in chat_history]
            assistant_reply = await _get_llm().multi_turn_query(
                context=context,
                question=req.message,
                system_prompt=system_prompt,
                chat_history=history_dicts,
            )
        else:
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
    finally:
        # SearchClient owns an httpx.AsyncClient — a per-request leak here
        # eventually exhausts the default connection pool under load.
        if search_client is not None:
            try:
                await search_client.close()
            except Exception:
                logger.debug("SearchClient close failed", exc_info=True)

    citations = _parse_citations(assistant_reply)
    metadata: dict[str, object] = {}
    if citations:
        metadata["citations"] = citations
    if tool_calls:
        metadata["tool_calls"] = tool_calls
    assistant_message = ChatMessage(
        meeting_id=meeting_id,
        user_id=current_user.id,
        role="assistant",
        content=assistant_reply,
        message_metadata=_json.dumps(metadata) if metadata else None,
    )
    db.add(assistant_message)
    await db.flush()
    await db.commit()

    follow_ups = await _generate_follow_ups(assistant_reply)

    return {
        "user_message": _message_response_model(user_message),
        "assistant_message": _message_response_model(assistant_message),
        "follow_ups": follow_ups,
    }


@router.post("/meetings/{meeting_id}/chat/stream")
async def stream_chat_message(
    meeting_id: UUID,
    req: ChatSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming version of chat. Yields sentences as they're generated."""
    from app.models.database import AsyncSessionLocal

    await _check_rate_limit(str(current_user.id))
    meeting = await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    # Pre-compute everything that needs the request-scoped db session
    user_message = ChatMessage(
        meeting_id=meeting_id,
        user_id=current_user.id,
        role="user",
        content=req.message,
    )
    db.add(user_message)
    await db.flush()

    chat_history = await _get_recent_chat_history(meeting_id=meeting_id, db=db)
    context = await _build_chat_context(
        meeting=meeting,
        chat_history=chat_history,
        db=db,
        user_question=req.message,
    )
    system_prompt = _build_system_prompt_for_meeting(meeting)
    # Capture IDs before the request-scoped session closes
    user_message_id = str(user_message.id)
    user_id = current_user.id
    await db.commit()

    async def event_generator():
        full_response = ""
        tool_calls: list[dict] = []
        complexity = classify_chat_complexity(req.message)
        use_tools = _should_use_tools(req.message)
        search_client = None
        try:
            if use_tools:
                from app.core.search import SearchClient

                search_client = SearchClient()

                async def _exec_tool(name: str, inp: dict) -> str:
                    return await execute_tool(
                        name,
                        inp,
                        search_client=search_client,
                        rag_pipeline=_get_rag(),
                        db=None,
                        meeting_id=meeting_id,
                    )

                full_response, tool_calls = await _get_llm().tool_use_query(
                    context=context,
                    question=req.message,
                    system_prompt=system_prompt,
                    tools=CHAT_TOOLS,
                    tool_executor=_exec_tool,
                )
                yield f"data: {_json.dumps({'type': 'token', 'content': full_response})}\n\n"
            elif complexity == "complex" and chat_history:
                history_dicts = [{"role": message.role, "content": message.content} for message in chat_history]
                full_response = await _get_llm().multi_turn_query(
                    context=context,
                    question=req.message,
                    system_prompt=system_prompt,
                    chat_history=history_dicts,
                )
                yield f"data: {_json.dumps({'type': 'token', 'content': full_response})}\n\n"
            else:
                async for sentence in _get_llm().async_query_stream(
                    context=context,
                    question=req.message,
                    system_prompt=system_prompt,
                ):
                    if full_response:
                        full_response += " "
                    full_response += sentence
                    yield f"data: {_json.dumps({'type': 'token', 'content': sentence})}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("LLM stream failed for meeting %s", meeting_id)
            yield (
                f"data: {_json.dumps({'type': 'error', 'content': 'AI service temporarily unavailable.'})}\n\n"
            )
            return
        finally:
            # SearchClient owns an httpx.AsyncClient — per-stream leaks exhaust
            # the default connection pool if left dangling.
            if search_client is not None:
                try:
                    await search_client.close()
                except Exception:
                    logger.debug("SearchClient close failed", exc_info=True)

        # Use a dedicated session for the post-stream DB write so we don't
        # depend on the request-scoped session that may already be closed.
        assistant_content = full_response.strip()
        citations = _parse_citations(assistant_content)
        metadata: dict[str, object] = {}
        if citations:
            metadata["citations"] = citations
        if tool_calls:
            metadata["tool_calls"] = tool_calls
        async with AsyncSessionLocal() as stream_db:
            assistant_message = ChatMessage(
                meeting_id=meeting_id,
                user_id=user_id,
                role="assistant",
                content=assistant_content,
                message_metadata=_json.dumps(metadata) if metadata else None,
            )
            stream_db.add(assistant_message)
            await stream_db.flush()
            assistant_message_id = str(assistant_message.id)
            await stream_db.commit()

        follow_ups = await _generate_follow_ups(assistant_content)

        yield (
            "data: "
            + _json.dumps(
                {
                    "type": "done",
                    "user_message_id": user_message_id,
                    "assistant_message_id": assistant_message_id,
                    "follow_ups": follow_ups,
                    "citations": citations or None,
                    "tool_calls": tool_calls or None,
                }
            )
            + "\n\n"
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat/cross-meeting", response_model=ChatResponse)
async def cross_meeting_chat(
    req: CrossMeetingChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Chat across multiple meetings using summaries + RAG."""
    await _check_rate_limit(str(current_user.id))

    if req.meeting_ids:
        summary_result = await db.execute(
            select(MeetingSummary)
            .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
            .where(Meeting.user_id == current_user.id, Meeting.id.in_(req.meeting_ids))
            .order_by(MeetingSummary.created_at.desc())
        )
    else:
        summary_result = await db.execute(
            select(MeetingSummary)
            .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
            .where(Meeting.user_id == current_user.id)
            .order_by(MeetingSummary.created_at.desc())
            .limit(10)
        )
    summaries = summary_result.scalars().all()

    context_parts: list[str] = []
    for summary in summaries:
        section = f"## Meeting ({summary.created_at.strftime('%Y-%m-%d')})\n{summary.content}"
        if summary.key_points:
            section += f"\n### Key Points\n{_format_summary_field(summary.key_points)}"
        if summary.decisions:
            section += f"\n### Decisions\n{_format_summary_field(summary.decisions)}"
        if summary.action_items:
            section += f"\n### Action Items\n{_format_summary_field(summary.action_items)}"
        context_parts.append(section)

    try:
        rag = _get_rag()
        rag_where: dict = {"user_id": str(current_user.id)}
        if req.meeting_ids:
            allowed_meeting_ids = [str(mid) for mid in req.meeting_ids]
            rag_where = {
                "$and": [
                    {"user_id": str(current_user.id)},
                    {"meeting_id": {"$in": allowed_meeting_ids}},
                ]
            }
        rag_results = rag.hybrid_search(query=req.message, top_k=8, where=rag_where)
        if rag_results:
            passages = []
            for chunk in rag_results[:8]:
                meta = chunk.get("metadata", {})
                source = meta.get("source_type", "unknown")
                speaker = meta.get("speaker", "")
                meeting_date = meta.get("meeting_date") or meta.get("meeting_id", "")
                prefix = f"[{source}: {speaker}]" if speaker else f"[{source}]"
                if meeting_date:
                    prefix = f"{prefix} ({meeting_date})"
                passages.append(f"{prefix} {chunk['text']}")
            context_parts.append("## Relevant Passages (across meetings)\n" + "\n\n".join(passages))
    except Exception:
        logger.warning("Cross-meeting RAG search failed", exc_info=True)

    context = "\n\n".join(context_parts) if context_parts else "No meeting summaries available yet."

    agent_result = await db.execute(
        select(Agent).where(Agent.user_id == current_user.id, Agent.is_primary.is_(True))
    )
    agent = agent_result.scalar_one_or_none()
    system_prompt = (
        (agent.system_prompt if agent and agent.system_prompt else None)
        or build_system_prompt(
            getattr(agent, "mode", "general"),
            getattr(agent, "description", ""),
            getattr(agent, "persona_id", "general"),
        )
    )
    system_prompt += (
        "\n\nYou are answering questions that span multiple meetings. "
        "Compare, contrast, and synthesize information across meetings. "
        "Reference which meeting date each piece of information comes from."
    )

    try:
        reply = await _get_llm().async_query(
            context=context,
            question=req.message,
            system_prompt=system_prompt,
        )
    except Exception:
        logger.exception("Cross-meeting LLM query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable.",
        )

    follow_ups = await _generate_follow_ups(reply)
    now = datetime.now(timezone.utc)
    return {
        "user_message": ChatMessageResponse(
            id=uuid4(),
            role="user",
            content=req.message,
            created_at=now,
        ),
        "assistant_message": ChatMessageResponse(
            id=uuid4(),
            role="assistant",
            content=reply,
            created_at=now,
        ),
        "follow_ups": follow_ups,
    }


@router.get("/meetings/{meeting_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    meeting_id: UUID,
    per_page: int = Query(default=50, ge=1, le=100),
    before: datetime | None = Query(default=None, description="Cursor: load messages before this timestamp"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest N messages in chronological order.

    Default (no ``before``): fetch newest ``per_page`` via DESC then reverse.
    With ``before``: fetch messages older than the cursor (for scroll-up).
    """
    await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    # Single round-trip: use COUNT(*) OVER() as a window function alongside
    # the page fetch. Previous version ran COUNT(*) and SELECT as two
    # separate queries on every history page load.
    total_col = func.count().over().label("total")
    query = select(ChatMessage, total_col).where(ChatMessage.meeting_id == meeting_id)

    if before is not None:
        # Normalize tz-aware to naive UTC for DB comparison
        if before.tzinfo is not None:
            before = before.astimezone(timezone.utc).replace(tzinfo=None)
        query = query.where(ChatMessage.created_at < before)

    query = query.order_by(ChatMessage.created_at.desc()).limit(per_page)
    result = await db.execute(query)
    rows = result.all()
    total = rows[0].total if rows else 0
    # Fetch newest N by DESC then reverse for chronological render
    messages = list(reversed([row.ChatMessage for row in rows]))

    return ChatHistoryResponse(
        messages=[_enrich_message_response(message) for message in messages],
        meeting_id=meeting_id,
        total=total,
    )


@router.get("/meetings/{meeting_id}/chat/suggestions")
async def get_chat_suggestions(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return 3-4 contextual prompt suggestions for this meeting."""
    meeting = await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    cached = get_cached_suggestions(str(meeting_id))
    if cached:
        return {"suggestions": cached}

    summary_result = await db.execute(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
    )
    summary = summary_result.scalar_one_or_none()

    summary_content = summary.content if summary else None
    transcript_tail = meeting.transcript[-2000:] if meeting.transcript else None

    suggestions = await generate_suggestions(
        summary_content=summary_content,
        transcript_tail=transcript_tail,
        llm_query_fn=_get_llm().async_query,
    )

    cache_suggestions(str(meeting_id), suggestions)
    return {"suggestions": suggestions}


@router.get("/meetings/{meeting_id}/chat/insights/stream")
async def stream_insights(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream of proactive insights during a live meeting."""
    meeting = await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    if meeting.status not in ("active", "joining"):
        raise HTTPException(status_code=400, detail="Meeting is not live.")

    async def event_generator():
        async for insight in subscribe_insights(str(meeting_id)):
            yield f"data: {_json.dumps(insight)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/meetings/{meeting_id}/chat/export")
async def export_chat(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export chat history as markdown."""
    meeting = await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.meeting_id == meeting_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()

    if not messages:
        return PlainTextResponse("No chat messages to export.", media_type="text/plain")

    lines = [f"# Chat Notes - {meeting.platform or 'Meeting'}", ""]
    for msg in messages:
        time_str = msg.created_at.strftime("%I:%M %p") if msg.created_at else ""
        speaker = "You" if msg.role == "user" else "Cognara"
        lines.append(f"**{speaker}** ({time_str}):")
        lines.append(msg.content)
        lines.append("")

    markdown = "\n".join(lines)
    return PlainTextResponse(
        markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="chat-notes-{meeting_id}.md"'},
    )


@router.post("/meetings/{meeting_id}/chat/add-to-report")
async def add_chat_to_report(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Distill chat insights and append to the meeting summary."""
    meeting = await _get_meeting_or_raise(meeting_id=meeting_id, current_user=current_user, db=db)

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.meeting_id == meeting_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    if not messages:
        raise HTTPException(status_code=400, detail="No chat messages to add.")

    chat_text = "\n".join(
        f"{'User' if message.role == 'user' else 'Assistant'}: {message.content}"
        for message in messages
    )
    try:
        insights = await _get_llm().async_query(
            context=chat_text[:4000],
            question=(
                "Distill the key insights, decisions, and action items from this chat conversation into "
                "a concise summary section. Format with bullet points."
            ),
            system_prompt="You summarize chat conversations into actionable meeting insights.",
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to generate insights.")

    summary_result = await db.execute(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
    )
    summary = summary_result.scalar_one_or_none()
    if summary is None:
        raise HTTPException(status_code=404, detail="No meeting summary exists yet.")

    summary.content = f"{summary.content}\n\n## Chat Insights\n{insights}"
    await db.commit()
    return {"status": "added", "insights": insights}
