"""Tool definitions and executors for chat tool-use with Claude."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CHAT_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current information about a topic discussed in the meeting",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "document_lookup",
        "description": "Search uploaded meeting documents for specific information",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in the documents"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_action_item",
        "description": "Create an action item or task from the meeting discussion",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "The action item description"},
                "assignee": {"type": "string", "description": "Who is responsible (optional)"},
            },
            "required": ["description"],
        },
    },
]


async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    search_client=None,
    rag_pipeline=None,
    db=None,
    meeting_id=None,
) -> str:
    """Execute a tool and return the result as a string for Claude."""
    if tool_name == "web_search" and search_client:
        try:
            query = str(tool_input.get("query", "")).strip()
            results = await search_client.search_formatted(query)
            return results if results else "No results found."
        except Exception as exc:
            logger.warning("Web search tool failed: %s", exc)
            return f"Search failed: {exc}"

    if tool_name == "document_lookup" and rag_pipeline:
        try:
            query = str(tool_input.get("query", "")).strip()
            chunks = rag_pipeline.hybrid_search(query=query, top_k=5)
            meeting_id_str = str(meeting_id) if meeting_id is not None else None
            agent_id_str = None
            if db is not None and meeting_id is not None:
                from sqlalchemy import select
                from app.models.database import Meeting

                result = await db.execute(select(Meeting.agent_id).where(Meeting.id == meeting_id))
                agent_id = result.scalar_one_or_none()
                if agent_id is not None:
                    agent_id_str = str(agent_id)

            if meeting_id_str is not None or agent_id_str is not None:
                chunks = [
                    chunk
                    for chunk in chunks
                    if chunk.get("metadata", {}).get("source_type") == "document"
                    and (
                        (meeting_id_str is not None and chunk.get("metadata", {}).get("meeting_id") == meeting_id_str)
                        or (agent_id_str is not None and chunk.get("metadata", {}).get("agent_id") == agent_id_str)
                    )
                ]
            if not chunks:
                return "No relevant document passages found."

            lines: list[str] = []
            for chunk in chunks[:5]:
                meta = chunk.get("metadata", {})
                filename = meta.get("filename", "document")
                page = meta.get("page_number", "")
                prefix = f"[{filename} p.{page}]" if page else f"[{filename}]"
                lines.append(f"{prefix} {chunk['text']}")
            return "\n\n".join(lines)
        except Exception as exc:
            logger.warning("Document lookup tool failed: %s", exc)
            return f"Document search failed: {exc}"

    if tool_name == "create_action_item":
        description = str(tool_input.get("description", "")).strip()
        assignee = str(tool_input.get("assignee", "")).strip()
        result = f"Action item created: {description}"
        if assignee:
            result += f" (assigned to {assignee})"
        return result

    return f"Unknown tool: {tool_name}"
