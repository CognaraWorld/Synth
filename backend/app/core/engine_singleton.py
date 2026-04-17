"""Single shared BotEngine instance for the current process."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.bot_engine import BotEngine

logger = logging.getLogger(__name__)

_engine: "BotEngine | None" = None


def get_engine() -> "BotEngine":
    """Return the process-wide BotEngine singleton."""
    global _engine
    if _engine is None:
        from app.core.bot_engine import BotEngine

        _engine = BotEngine()
        logger.info("BotEngine singleton initialized")
    return _engine


def set_engine(engine: "BotEngine | None") -> None:
    """Override the process-wide BotEngine singleton."""
    global _engine
    _engine = engine
