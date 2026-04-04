import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import get_settings
from app.models.database import engine, Base
from app.models.credit_transaction import CreditTransaction  # noqa: F401 — register model
from app.api.routes import auth, agents, meetings, documents, payments, credits, webhook
from app.api.websocket import router as ws_router

logger = logging.getLogger(__name__)
settings = get_settings()


def _run_migrations(connection):
    """Add missing columns to existing tables for backwards compatibility."""
    inspector = inspect(connection)
    if inspector.has_table("documents"):
        columns = [c["name"] for c in inspector.get_columns("documents")]
        if "doc_summary" not in columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN doc_summary TEXT"))
            logger.info("Migration: added doc_summary column to documents table")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # Create new tables
        await conn.run_sync(Base.metadata.create_all)
        # Backfill missing columns on existing tables
        await conn.run_sync(_run_migrations)

    # Pre-load TTS + filler cache in background thread so first meeting
    # doesn't block for ~3s while Kokoro loads
    import asyncio
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _preload_tts)

    yield
    await engine.dispose()


def _preload_tts():
    """Load TTS model and pre-synthesize filler phrases at startup."""
    try:
        from app.core.tts import TextToSpeech
        from app.utils.filler import FillerManager
        from app.api.routes.webhook import get_bot_engine

        engine = get_bot_engine()
        if not engine._tts:
            logger.info("Pre-loading TTS model at startup...")
            engine._tts = TextToSpeech(voice="am_michael", sample_rate=24000, speed=1.1)
            engine._filler_manager.preload(engine._tts)
            engine._models_loaded = True
            logger.info("TTS model and filler cache ready")
    except Exception as exc:
        logger.warning("TTS preload failed (will retry on first use): %s", exc)


app = FastAPI(
    title="Synth API",
    description="AI Meeting Participant Bot - Backend API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(webhook.router, prefix="/api")
app.include_router(ws_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "synth-api"}
