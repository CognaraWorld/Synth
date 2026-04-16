"""Rate limiter with in-memory fallback and optional Redis backend."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_CHAT_RATE_LIMIT = 20
_WINDOW_SECONDS = 60


class InMemoryRateLimiter:
    """Sliding window rate limiter using in-memory dict. Single-process only."""

    _MAX_BUCKETS = 10_000

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup: float = 0.0

    async def check(self, user_id: str) -> None:
        now = datetime.now(timezone.utc).timestamp()
        async with self._lock:
            # Periodic cleanup: evict stale buckets every 5 minutes
            if now - self._last_cleanup > 300 or len(self._buckets) > self._MAX_BUCKETS:
                stale = [uid for uid, ts_list in self._buckets.items() if not ts_list or now - ts_list[-1] >= _WINDOW_SECONDS]
                for uid in stale:
                    del self._buckets[uid]
                self._last_cleanup = now

            bucket = [timestamp for timestamp in self._buckets.get(user_id, []) if now - timestamp < _WINDOW_SECONDS]
            if len(bucket) >= _CHAT_RATE_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Chat rate limit exceeded. Max {_CHAT_RATE_LIMIT} messages per minute.",
                )
            bucket.append(now)
            self._buckets[user_id] = bucket


class RedisRateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets. Multi-process safe."""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def check(self, user_id: str) -> None:
        import time

        key = f"chat:ratelimit:{user_id}"
        now = time.time()
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, "-inf", now - _WINDOW_SECONDS)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, _WINDOW_SECONDS + 5)
        results = await pipe.execute()
        count = results[1]
        if count >= _CHAT_RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Chat rate limit exceeded. Max {_CHAT_RATE_LIMIT} messages per minute.",
            )


_limiter: InMemoryRateLimiter | RedisRateLimiter | None = None


def get_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    global _limiter

    if _limiter is None:
        from app.config import get_settings

        settings = get_settings()
        redis_url = getattr(settings, "redis_url", None)
        if redis_url:
            logger.info("Using Redis rate limiter at %s", redis_url)
            _limiter = RedisRateLimiter(redis_url)
        else:
            logger.info("Using in-memory rate limiter (single process only)")
            _limiter = InMemoryRateLimiter()

    return _limiter
