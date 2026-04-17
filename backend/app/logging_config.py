"""Structured JSON logging configuration for Synth backend.

Provides consistent JSON-formatted logs with per-request context fields
(session_id, bot_id) for production observability.
"""

from __future__ import annotations

import logging
import logging.config


_PLAIN_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "stream": "ext://sys.stdout",
        },
        "json_console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "app": {
            "level": "INFO",
            "propagate": True,
        },
        "uvicorn.access": {
            "level": "WARNING",
            "propagate": True,
        },
    },
}

_JSON_LOGGING_CONFIG = {
    **_PLAIN_LOGGING_CONFIG,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "json_console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["json_console"],
    },
}


def configure_logging(json_output: bool = False) -> None:
    """Apply logging configuration.

    Args:
        json_output: When True, emit JSON-structured logs (for production).
            When False, use human-readable plain text (for development).
    """
    if json_output:
        try:
            from pythonjsonlogger.jsonlogger import JsonFormatter  # noqa: F401
        except ImportError:
            logging.config.dictConfig(_PLAIN_LOGGING_CONFIG)
            logging.getLogger(__name__).warning(
                "python-json-logger not installed; using plain text logging. "
                "Install with: pip install python-json-logger"
            )
            return
        logging.config.dictConfig(_JSON_LOGGING_CONFIG)
        return

    logging.config.dictConfig(_PLAIN_LOGGING_CONFIG)
