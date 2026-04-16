"""In-process pub/sub for routing insight_detector results to SSE endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

_subscribers: dict[str, list[asyncio.Queue]] = {}


async def subscribe(meeting_id: str) -> AsyncIterator[dict]:
    """Subscribe to insights for a meeting. Yields insight dicts."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(meeting_id, []).append(queue)
    try:
        while True:
            insight = await queue.get()
            if insight is None:
                break
            yield insight
    finally:
        subscribers = _subscribers.get(meeting_id, [])
        if queue in subscribers:
            subscribers.remove(queue)
        if not subscribers:
            _subscribers.pop(meeting_id, None)


async def publish(meeting_id: str, insight: dict) -> None:
    """Publish an insight to all subscribers for a meeting."""
    for queue in _subscribers.get(meeting_id, []):
        try:
            queue.put_nowait(insight)
        except asyncio.QueueFull:
            logger.warning("Insight queue full for meeting %s, dropping", meeting_id)


async def close_meeting(meeting_id: str) -> None:
    """Signal all subscribers that the meeting has ended."""
    for queue in _subscribers.get(meeting_id, []):
        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
    _subscribers.pop(meeting_id, None)
