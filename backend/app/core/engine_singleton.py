"""Single shared BotEngine instance for the current process."""

from __future__ import annotations

import logging
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.bot_engine import BotEngine

logger = logging.getLogger(__name__)

_engine: "BotEngine | None" = None
_engine_lock = Lock()


def get_engine() -> "BotEngine":
    """Return the process-wide BotEngine singleton."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from app.core.bot_engine import BotEngine

                _engine = BotEngine()
                logger.info("BotEngine singleton initialized")
    return _engine


def get_engine_if_initialized() -> "BotEngine | None":
    """Return the process-wide BotEngine if it already exists."""
    return _engine


def set_engine(engine: "BotEngine | None") -> None:
    """Override the process-wide BotEngine singleton."""
    global _engine
    with _engine_lock:
        _engine = engine
