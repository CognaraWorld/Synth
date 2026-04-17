"""Prometheus metrics for Synth backend.

Exposes counters, gauges, and histograms for bot engine, LLM, and
webhook processing. Wired into FastAPI via prometheus-fastapi-instrumentator.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazy-import Prometheus client so the app starts without it installed
try:
    from prometheus_client import Counter, Gauge, Histogram

    meetings_active = Gauge(
        "synth_meetings_active",
        "Number of currently active bot sessions",
    )
    questions_processed_total = Counter(
        "synth_questions_processed_total",
        "Total questions handled by the bot engine",
    )
    llm_calls_total = Counter(
        "synth_llm_calls_total",
        "Total LLM API calls",
        ["provider"],
    )
    llm_fallbacks_total = Counter(
        "synth_llm_fallbacks_total",
        "Total times Gemini fell back to Claude",
    )
    tts_synthesis_seconds = Histogram(
        "synth_tts_synthesis_seconds",
        "TTS synthesis latency in seconds",
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )
    webhook_queue_depth = Gauge(
        "synth_webhook_queue_depth",
        "Current webhook semaphore concurrency in use",
    )

    _PROMETHEUS_AVAILABLE = True
    logger.info("Prometheus metrics initialized")

except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.warning(
        "prometheus_client not installed; metrics disabled. "
        "Install with: pip install prometheus-client"
    )

    class _NoOp:
        """No-op stub so callers don't need to check _PROMETHEUS_AVAILABLE."""
        def inc(self, *a, **kw): pass
        def dec(self, *a, **kw): pass
        def set(self, *a, **kw): pass
        def observe(self, *a, **kw): pass
        def labels(self, *a, **kw): return self
        def time(self): return _NoOpContext()

    class _NoOpContext:
        def __enter__(self): return self
        def __exit__(self, *a): pass

    _noop = _NoOp()
    meetings_active = _noop  # type: ignore[assignment]
    questions_processed_total = _noop  # type: ignore[assignment]
    llm_calls_total = _noop  # type: ignore[assignment]
    llm_fallbacks_total = _noop  # type: ignore[assignment]
    tts_synthesis_seconds = _noop  # type: ignore[assignment]
    webhook_queue_depth = _noop  # type: ignore[assignment]


def setup_prometheus(app) -> None:
    """Wire prometheus-fastapi-instrumentator into the FastAPI app."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
        logger.info("Prometheus /metrics endpoint exposed")
    except ImportError:
        logger.warning(
            "prometheus-fastapi-instrumentator not installed; /metrics not exposed. "
            "Install with: pip install prometheus-fastapi-instrumentator"
        )
    except Exception as exc:
        logger.warning("Failed to set up Prometheus instrumentation: %s", exc)
