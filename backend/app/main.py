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


def _add_column_if_missing(
    connection,
    table_name: str,
    columns: dict[str, dict],
    column_name: str,
    ddl: str,
) -> None:
    if column_name in columns:
        return
    connection.execute(text(ddl))
    logger.info("Migration: added %s column to %s table", column_name, table_name)


def _get_columns(inspector, table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def _run_migrations(connection):
    """Add missing columns to existing tables for backwards compatibility."""
    inspector = inspect(connection)
    dialect_name = connection.dialect.name

    if inspector.has_table("documents"):
        document_columns = _get_columns(inspector, "documents")
        _add_column_if_missing(
            connection=connection,
            table_name="documents",
            columns=document_columns,
            column_name="doc_summary",
            ddl="ALTER TABLE documents ADD COLUMN doc_summary TEXT",
        )

    if inspector.has_table("users"):
        user_columns = _get_columns(inspector, "users")
        _add_column_if_missing(
            connection=connection,
            table_name="users",
            columns=user_columns,
            column_name="provider",
            ddl="ALTER TABLE users ADD COLUMN provider VARCHAR(50)",
        )
        _add_column_if_missing(
            connection=connection,
            table_name="users",
            columns=user_columns,
            column_name="credits",
            ddl="ALTER TABLE users ADD COLUMN credits INTEGER",
        )
        connection.execute(text("UPDATE users SET provider = 'email' WHERE provider IS NULL"))
        logger.info("Migration: backfilled users.provider to 'email' for NULL rows")
        connection.execute(text("UPDATE users SET credits = 3 WHERE credits IS NULL"))
        logger.info("Migration: backfilled users.credits to 3 for NULL rows")
        if dialect_name == "postgresql":
            connection.execute(text("ALTER TABLE users ALTER COLUMN provider SET DEFAULT 'email'"))
            connection.execute(text("ALTER TABLE users ALTER COLUMN credits SET DEFAULT 3"))
            connection.execute(text("ALTER TABLE users ALTER COLUMN provider SET NOT NULL"))
            connection.execute(text("ALTER TABLE users ALTER COLUMN credits SET NOT NULL"))
            logger.info("Migration: enforced users.provider/users.credits defaults and NOT NULL")

    if inspector.has_table("credit_transactions"):
        credit_columns = _get_columns(inspector, "credit_transactions")
        had_balance_after_column = "balance_after" in credit_columns
        balance_after_was_nullable = credit_columns.get("balance_after", {}).get("nullable", True)
        meeting_id_type = "UUID" if dialect_name == "postgresql" else "VARCHAR(36)"
        _add_column_if_missing(
            connection=connection,
            table_name="credit_transactions",
            columns=credit_columns,
            column_name="meeting_id",
            ddl=f"ALTER TABLE credit_transactions ADD COLUMN meeting_id {meeting_id_type}",
        )
        _add_column_if_missing(
            connection=connection,
            table_name="credit_transactions",
            columns=credit_columns,
            column_name="amount",
            ddl="ALTER TABLE credit_transactions ADD COLUMN amount INTEGER DEFAULT 0",
        )
        _add_column_if_missing(
            connection=connection,
            table_name="credit_transactions",
            columns=credit_columns,
            column_name="transaction_type",
            ddl="ALTER TABLE credit_transactions ADD COLUMN transaction_type VARCHAR(50) DEFAULT 'legacy'",
        )
        _add_column_if_missing(
            connection=connection,
            table_name="credit_transactions",
            columns=credit_columns,
            column_name="description",
            ddl="ALTER TABLE credit_transactions ADD COLUMN description VARCHAR(500) DEFAULT 'Legacy credit transaction'",
        )
        _add_column_if_missing(
            connection=connection,
            table_name="credit_transactions",
            columns=credit_columns,
            column_name="balance_after",
            ddl="ALTER TABLE credit_transactions ADD COLUMN balance_after INTEGER",
        )
        _add_column_if_missing(
            connection=connection,
            table_name="credit_transactions",
            columns=credit_columns,
            column_name="stripe_session_id",
            ddl="ALTER TABLE credit_transactions ADD COLUMN stripe_session_id VARCHAR(255)",
        )
        connection.execute(
            text("UPDATE credit_transactions SET amount = 0 WHERE amount IS NULL")
        )
        connection.execute(
            text(
                "UPDATE credit_transactions "
                "SET transaction_type = 'legacy' "
                "WHERE transaction_type IS NULL OR transaction_type = ''"
            )
        )
        connection.execute(
            text(
                "UPDATE credit_transactions "
                "SET description = 'Legacy credit transaction' "
                "WHERE description IS NULL OR description = ''"
            )
        )
        connection.execute(
            text(
                "UPDATE credit_transactions "
                "SET balance_after = COALESCE(balance_after, amount, 0) "
                "WHERE balance_after IS NULL"
            )
        )
        if dialect_name == "postgresql" and (not had_balance_after_column or balance_after_was_nullable):
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN balance_after SET NOT NULL")
            )
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN amount SET NOT NULL")
            )
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN transaction_type SET NOT NULL")
            )
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN description SET NOT NULL")
            )
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN amount SET DEFAULT 0")
            )
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN balance_after SET DEFAULT 0")
            )
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN transaction_type SET DEFAULT 'legacy'")
            )
            connection.execute(
                text(
                    "ALTER TABLE credit_transactions "
                    "ALTER COLUMN description SET DEFAULT 'Legacy credit transaction'"
                )
            )
            logger.info(
                "Migration: normalized credit_transactions defaults and NOT NULL constraints"
            )

        if (
            dialect_name == "postgresql"
            and "meeting_id" in credit_columns
            and not credit_columns["meeting_id"].get("nullable", True)
        ):
            connection.execute(
                text("ALTER TABLE credit_transactions ALTER COLUMN meeting_id DROP NOT NULL")
            )
            logger.info(
                "Migration: dropped NOT NULL on meeting_id for credit_transactions table"
            )

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
            default_voice = "am_michael"  # default persona voice
            try:
                from app.utils.bot_profiles import get_persona_tts_voice
                default_voice = get_persona_tts_voice("general")
            except ImportError:
                pass
            engine._tts = TextToSpeech(voice=default_voice, sample_rate=24000, speed=1.1)
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
