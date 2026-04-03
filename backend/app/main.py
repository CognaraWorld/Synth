import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import get_settings
from app.models.database import engine, Base
from app.models.credit_transaction import CreditTransaction  # noqa: F401 — register model
from app.api.routes import auth, agents, bot, meetings, documents, payments, credits
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
            connection.execute(text("ALTER TABLE credit_transactions ADD COLUMN meeting_id UUID"))
            logger.info("Migration: added meeting_id column to credit_transactions table")
    if inspector.has_table("agents"):
        columns = [c["name"] for c in inspector.get_columns("agents")]
        if "voice" not in columns:
            connection.execute(
                text("ALTER TABLE agents ADD COLUMN voice VARCHAR(32) NOT NULL DEFAULT 'female'")
            )
            logger.info("Migration: added voice column to agents table")
        if "response_mode" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE agents ADD COLUMN response_mode VARCHAR(32) "
                    "NOT NULL DEFAULT 'name_only'"
                )
            )
            logger.info("Migration: added response_mode column to agents table")
        if "is_primary" not in columns:
            connection.execute(
                text("ALTER TABLE agents ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT FALSE")
            )
            connection.execute(
                text(
                    "WITH ranked AS ("
                    " SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC, id DESC) AS rank"
                    " FROM agents"
                    ") "
                    "UPDATE agents "
                    "SET is_primary = CASE WHEN ranked.rank = 1 THEN TRUE ELSE FALSE END "
                    "FROM ranked "
                    "WHERE agents.id = ranked.id"
                )
            )
            logger.info("Migration: added is_primary column to agents table")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # Create new tables
        await conn.run_sync(Base.metadata.create_all)
        # Backfill missing columns on existing tables
        await conn.run_sync(_run_migrations)
    yield
    await engine.dispose()


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
app.include_router(bot.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(ws_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "synth-api"}
