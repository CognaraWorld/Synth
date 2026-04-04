import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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

    if inspector.has_table("credit_transactions"):
        columns = [c["name"] for c in inspector.get_columns("credit_transactions")]
        if "meeting_id" not in columns:
            connection.execute(text(
                "ALTER TABLE credit_transactions ADD COLUMN meeting_id UUID REFERENCES meetings(id)"
            ))
            logger.info("Migration: added meeting_id column to credit_transactions table")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate critical configuration at startup
    is_prod = settings.environment == "production"

    if settings.secret_key == "change-me-in-production":
        if is_prod:
            raise RuntimeError("FATAL: Set SECRET_KEY before running in production")
        logger.warning("Using default secret key. Set SECRET_KEY in production!")

    required_keys = {
        "RECALL_API_KEY": settings.recall_api_key,
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
    }
    missing = [k for k, v in required_keys.items() if not v]
    if missing:
        if is_prod:
            raise RuntimeError(f"FATAL: Missing required config: {', '.join(missing)}")
        logger.error("Missing required configuration: %s", ", ".join(missing))

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

# CORS: restrict to configured origins instead of wildcard
# (OWASP A05:2021 - Security Misconfiguration)
origins = [o.strip() for o in settings.cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject standard security headers on every response.

    - X-Content-Type-Options: prevents MIME-sniffing attacks
    - X-Frame-Options: prevents clickjacking via iframes
    - Referrer-Policy: limits referrer leakage to cross-origin requests
    - Permissions-Policy: disables unused browser features
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    return response


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
