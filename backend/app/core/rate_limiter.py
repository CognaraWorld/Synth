"""Rate limiter with in-memory fallback and optional Redis backend.

Supports the default chat-style limiter used by ``get_rate_limiter()``
plus named limiters (e.g. login, register, service-token) with their
own limits + window. Named limiters share the same in-memory storage
so they all participate in periodic cleanup.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_CHAT_RATE_LIMIT = 20
_WINDOW_SECONDS = 60


# Named limits used by non-chat endpoints. Keep these tight — they protect
# auth and payment surfaces against brute force / enumeration.
NAMED_LIMITS: dict[str, tuple[int, int]] = {
    "login": (5, 900),              # 5 attempts / 15 min
    "register": (3, 3600),          # 3 / hour
    "service-token": (5, 60),       # 5 / minute
    "create-checkout": (10, 3600),  # 10 / hour
    "create-meeting": (5, 60),      # 5 / minute
}


class InMemoryRateLimiter:
    """Sliding window rate limiter using in-memory dict. Single-process only."""

    _MAX_BUCKETS = 10_000

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup: float = 0.0

    async def check(
        self,
        key: str,
        *,
        limit: int = _CHAT_RATE_LIMIT,
        window_seconds: int = _WINDOW_SECONDS,
        detail: str | None = None,
    ) -> None:
        """Reject with 429 when *key* has made ``limit`` calls inside ``window_seconds``.

        ``key`` is the namespaced identifier (e.g. ``"login:1.2.3.4"``). Callers
        should include their own prefix so different endpoints don't share buckets.
        """
        now = datetime.now(timezone.utc).timestamp()
        async with self._lock:
            # Periodic cleanup: evict buckets whose newest entry has aged out
            # of *that bucket's own window*. Using the global max (3600s from
            # register) for all buckets kept 60s-window entries alive 60× too
            # long under many-IP load. We look the window up from the bucket
            # prefix (e.g. "login:1.2.3.4" → login window), and fall back to
            # the current call's window for unprefixed keys (chat).
            if now - self._last_cleanup > 300 or len(self._buckets) > self._MAX_BUCKETS:
                stale: list[str] = []
                for uid, ts_list in self._buckets.items():
                    if not ts_list:
                        stale.append(uid)
                        continue
                    # "<bucket>:<key>" → use NAMED_LIMITS window; bare keys
                    # (chat's raw user_id) use the current call's window.
                    prefix = uid.split(":", 1)[0] if ":" in uid else ""
                    bucket_window = (
                        NAMED_LIMITS[prefix][1] if prefix in NAMED_LIMITS else window_seconds
                    )
                    if now - ts_list[-1] >= bucket_window:
                        stale.append(uid)
                for uid in stale:
                    del self._buckets[uid]
                self._last_cleanup = now

            bucket = [
                timestamp
                for timestamp in self._buckets.get(key, [])
                if now - timestamp < window_seconds
            ]
            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=detail
                    or f"Rate limit exceeded. Max {limit} requests per {window_seconds}s.",
                )
            bucket.append(now)
            self._buckets[key] = bucket


class RedisRateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets. Multi-process safe."""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def check(
        self,
        key: str,
        *,
        limit: int = _CHAT_RATE_LIMIT,
        window_seconds: int = _WINDOW_SECONDS,
        detail: str | None = None,
    ) -> None:
        import time

        redis_key = f"ratelimit:{key}"
        now = time.time()
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, "-inf", now - window_seconds)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, window_seconds + 5)
        results = await pipe.execute()
        count = results[1]
        if count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail
                or f"Rate limit exceeded. Max {limit} requests per {window_seconds}s.",
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


async def check_named_limit(bucket: str, key: str) -> None:
    """Apply a named limit (e.g. ``"login"``) to ``key`` (e.g. an IP address).

    Raises HTTP 429 when the caller exceeds the configured rate.
    """
    if bucket not in NAMED_LIMITS:
        raise ValueError(f"Unknown rate-limit bucket: {bucket!r}")
    limit, window = NAMED_LIMITS[bucket]
    await get_rate_limiter().check(
        f"{bucket}:{key}",
        limit=limit,
        window_seconds=window,
        detail=f"Too many {bucket} attempts. Try again in {window}s.",
    )


def reset_for_tests() -> None:
    """Clear all rate-limit state. Unit tests only."""
    global _limiter
    if isinstance(_limiter, InMemoryRateLimiter):
        _limiter._buckets.clear()
        _limiter._last_cleanup = 0.0
    else:
        _limiter = None
