"""Short-lived single-use tickets for WebSocket authentication.

Why tickets instead of the raw JWT?
----------------------------------
The WebSocket endpoint requires auth in the URL (browsers can't set
custom headers on ``new WebSocket(...)``). Putting a long-lived JWT in
the URL means it appears in:

- Reverse-proxy / CDN access logs
- Browser history and the DevTools network panel
- Referer headers on any page the browser navigates to next

A 24-hour JWT leaking via any of these is a full account-access token.

Tickets shrink the blast radius:

- **60-second expiry.** A leaked ticket is useless after a minute.
- **Single-use.** Once the WebSocket validates it, the ticket is gone.
- **Bound to a user.** Consumes to the same ``user_id`` the JWT had.

This is the standard pattern used by AWS (pre-signed URLs), Twitch IRC
(CAP REQ auth tokens), and most multiplayer game lobbies.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from uuid import UUID

logger = logging.getLogger(__name__)


TICKET_TTL_SECONDS = 60
_MAX_OUTSTANDING_TICKETS = 10_000


# Simple in-memory store. Single-process only — if we ever run multiple
# backend workers we need Redis here. For now the ``engine_singleton``
# story already pins us to one worker, so this is consistent.
_tickets: dict[str, tuple[UUID, float]] = {}

# Deliberately a ``threading.Lock``, not ``asyncio.Lock``. Every operation
# here is a microsecond-scale dict lookup / mutation, so holding the lock
# never blocks the event loop in a way we'd notice. And because it is a
# threading lock, the store is safe to call from code running in a
# thread-executor (e.g. some of BotEngine's TTS/embedding paths) without
# having to build an async bridge. If any of these operations ever grows
# real I/O, switch to ``asyncio.Lock`` and make the callers async.
_lock = threading.Lock()
_last_cleanup: float = 0.0


def _sweep_expired_locked(now: float) -> None:
    """Remove expired tickets. Caller must hold ``_lock``."""
    global _last_cleanup
    # Amortize cleanup — run at most every 10s or when we're near the cap.
    if now - _last_cleanup < 10 and len(_tickets) < _MAX_OUTSTANDING_TICKETS:
        return
    expired = [tid for tid, (_, exp) in _tickets.items() if exp <= now]
    for tid in expired:
        del _tickets[tid]
    _last_cleanup = now


def issue_ticket(user_id: UUID) -> tuple[str, int]:
    """Mint a fresh ticket for ``user_id``.

    Returns ``(ticket, expires_in_seconds)``. Callers should hand the
    ticket back to the browser; the browser then includes it as the
    ``ticket`` query parameter when opening the WebSocket.
    """
    ticket = secrets.token_urlsafe(32)
    now = time.time()
    expiry = now + TICKET_TTL_SECONDS
    with _lock:
        _sweep_expired_locked(now)
        # Hard cap — if we're somehow at the ceiling, drop the oldest.
        if len(_tickets) >= _MAX_OUTSTANDING_TICKETS:
            oldest = min(_tickets, key=lambda t: _tickets[t][1])
            del _tickets[oldest]
            logger.warning("ws_tickets store at cap, evicted oldest ticket")
        _tickets[ticket] = (user_id, expiry)
    return ticket, TICKET_TTL_SECONDS


def consume_ticket(ticket: str) -> UUID | None:
    """Validate ``ticket`` exactly once. Returns the bound user_id or None.

    The ticket is removed from the store whether or not it was valid —
    this prevents replays even if the caller is retrying after a race.
    """
    if not ticket:
        return None
    now = time.time()
    with _lock:
        _sweep_expired_locked(now)
        entry = _tickets.pop(ticket, None)
    if entry is None:
        return None
    user_id, expiry = entry
    if expiry <= now:
        return None
    return user_id


def reset_for_tests() -> None:
    """Clear all tickets. Unit tests only."""
    global _last_cleanup
    with _lock:
        _tickets.clear()
        _last_cleanup = 0.0
