import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import get_settings
from app.models.database import engine, Base, DEFAULT_STARTER_CREDITS
from app.models.credit_transaction import CreditTransaction  # noqa: F401 — register model
from app.api.routes import auth, agents, bot, meetings, live, documents, payments, credits, webhook, reports, usage, chat
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
    # Inject IF NOT EXISTS for PostgreSQL so concurrent startup workers don't race
    if connection.dialect.name == "postgresql" and "ADD COLUMN" in ddl:
        ddl = ddl.replace("ADD COLUMN", "ADD COLUMN IF NOT EXISTS", 1)
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

    if inspector.has_table("meetings"):
        meeting_columns = _get_columns(inspector, "meetings")
        _add_column_if_missing(
            connection=connection,
            table_name="meetings",
            columns=meeting_columns,
            column_name="context_checkpoint",
            ddl="ALTER TABLE meetings ADD COLUMN context_checkpoint TEXT",
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
        connection.execute(
            text(f"UPDATE users SET credits = {DEFAULT_STARTER_CREDITS} WHERE credits IS NULL")
        )
        logger.info("Migration: backfilled users.credits to %d for NULL rows", DEFAULT_STARTER_CREDITS)
        if dialect_name == "postgresql":
            connection.execute(text("ALTER TABLE users ALTER COLUMN provider SET DEFAULT 'email'"))
            connection.execute(
                text(f"ALTER TABLE users ALTER COLUMN credits SET DEFAULT {DEFAULT_STARTER_CREDITS}")
            )
            connection.execute(text("ALTER TABLE users ALTER COLUMN provider SET NOT NULL"))
            connection.execute(text("ALTER TABLE users ALTER COLUMN credits SET NOT NULL"))
            logger.info("Migration: enforced users.provider/users.credits defaults and NOT NULL")

    if inspector.has_table("agents"):
        agent_columns = _get_columns(inspector, "agents")
        _add_column_if_missing(
            connection=connection,
            table_name="agents",
            columns=agent_columns,
            column_name="persona_id",
            ddl="ALTER TABLE agents ADD COLUMN persona_id VARCHAR(64)",
        )
        connection.execute(
            text(
                "UPDATE agents SET persona_id = 'general' "
                "WHERE persona_id IS NULL OR persona_id = '' "
                "OR persona_id NOT IN ('general','strategist','analyst','challenger','facilitator')"
            )
        )
        logger.info("Migration: backfilled agents.persona_id to 'general' where missing")
        connection.execute(text("UPDATE agents SET mode = 'general' WHERE mode IS NULL OR mode != 'general'"))
        connection.execute(
            text(
                "UPDATE agents SET voice = CASE persona_id "
                "WHEN 'strategist' THEN 'male' "
                "WHEN 'challenger' THEN 'male' "
                "ELSE 'female' END"
            )
        )
        logger.info("Migration: normalized agent mode and fixed persona voice mapping")
        if dialect_name == "postgresql":
            connection.execute(text("ALTER TABLE agents ALTER COLUMN persona_id SET DEFAULT 'general'"))
            connection.execute(text("ALTER TABLE agents ALTER COLUMN persona_id SET NOT NULL"))
            logger.info("Migration: enforced agents.persona_id default and NOT NULL")

    if inspector.has_table("meeting_overrides"):
        override_columns = _get_columns(inspector, "meeting_overrides")
        _add_column_if_missing(
            connection=connection,
            table_name="meeting_overrides",
            columns=override_columns,
            column_name="persona_id",
            ddl="ALTER TABLE meeting_overrides ADD COLUMN persona_id VARCHAR(64)",
        )
        connection.execute(
            text(
                "UPDATE meeting_overrides SET persona_id = 'general' "
                "WHERE persona_id IS NOT NULL "
                "AND persona_id NOT IN ('general','strategist','analyst','challenger','facilitator')"
            )
        )
        connection.execute(
            text(
                "UPDATE meeting_overrides SET mode = 'general' "
                "WHERE mode IS NOT NULL AND mode != 'general'"
            )
        )
        connection.execute(
            text(
                "UPDATE meeting_overrides SET voice = CASE persona_id "
                "WHEN 'strategist' THEN 'male' "
                "WHEN 'challenger' THEN 'male' "
                "ELSE 'female' END "
                "WHERE persona_id IS NOT NULL"
            )
        )

    if inspector.has_table("meeting_summaries"):
        summary_columns = _get_columns(inspector, "meeting_summaries")
        for col_name, ddl in [
            ("email_delivery_status", "ALTER TABLE meeting_summaries ADD COLUMN email_delivery_status VARCHAR(50) DEFAULT 'pending'"),
            ("email_delivered_at", "ALTER TABLE meeting_summaries ADD COLUMN email_delivered_at TIMESTAMP"),
            ("key_points", "ALTER TABLE meeting_summaries ADD COLUMN key_points TEXT"),
            ("action_items", "ALTER TABLE meeting_summaries ADD COLUMN action_items TEXT"),
            ("decisions", "ALTER TABLE meeting_summaries ADD COLUMN decisions TEXT"),
            ("pdf_path", "ALTER TABLE meeting_summaries ADD COLUMN pdf_path VARCHAR(1024)"),
            ("docx_path", "ALTER TABLE meeting_summaries ADD COLUMN docx_path VARCHAR(1024)"),
        ]:
            _add_column_if_missing(
                connection=connection,
                table_name="meeting_summaries",
                columns=summary_columns,
                column_name=col_name,
                ddl=ddl,
            )

    if inspector.has_table("credit_transactions"):
        credit_columns = _get_columns(inspector, "credit_transactions")
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
        if dialect_name == "postgresql":
            # Always ensure defaults (idempotent)
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
            # Per-column NOT NULL: check each independently so partial drift is always corrected
            # credit_columns reflects pre-migration state; missing columns default to nullable=True
            for _col in ("balance_after", "amount", "transaction_type", "description"):
                if credit_columns.get(_col, {}).get("nullable", True):
                    connection.execute(
                        text(f"ALTER TABLE credit_transactions ALTER COLUMN {_col} SET NOT NULL")
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

    # Stop orphaned Recall bots left running after server restart.
    # When --reload restarts the process, in-memory sessions are lost
    # but Recall bots keep running (and billing). This finds any
    # meetings still marked "active" in the DB and stops their bots.
    await _stop_orphaned_bots()

    # Pre-load TTS + filler cache in background thread so first meeting
    # doesn't block for ~3s while Kokoro loads
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _preload_tts)

    # Start background task to clean up stale bots
    cleanup_task = asyncio.create_task(_cleanup_stale_bots())

    yield

    cleanup_task.cancel()
    import contextlib
    with contextlib.suppress(asyncio.CancelledError):
        await cleanup_task
    await engine.dispose()


async def _stop_orphaned_bots():
    """Stop any Recall.ai bots left running after a server restart.

    Finds meetings stuck as 'active' in the DB and sends a leave
    command to their Recall bots, then reconciles the meeting records
    to a terminal state. This prevents billing leaks when uvicorn
    --reload restarts the process.
    """
    try:
        import math
        from datetime import datetime, timezone
        from app.models.database import Meeting, User, AsyncSessionLocal
        from app.meeting.recall_client import RecallClient
        from sqlalchemy import select, update

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Meeting).where(Meeting.status == "active")
            )
            orphans = result.scalars().all()

            if not orphans:
                return

            logger.warning("Found %d orphaned active meetings on startup — stopping their bots", len(orphans))
            recall = RecallClient()
            now = datetime.now(timezone.utc)
            try:
                for m in orphans:
                    # Stop the Recall bot if one exists
                    if m.bot_id:
                        try:
                            await recall.stop_bot(m.bot_id)
                            logger.info("Stopped orphaned bot %s for meeting %s", m.bot_id[:8], m.id)
                        except Exception as exc:
                            logger.debug("Orphaned bot %s already stopped: %s", m.bot_id[:8], exc)

                    # Reconcile DB state: transition to ended, set timestamps,
                    # and run idempotent billing settlement
                    duration_seconds = 0.0
                    if m.started_at:
                        duration_seconds = (now - m.started_at).total_seconds()
                    minutes_used = max(1, math.ceil(duration_seconds / 60)) if duration_seconds > 0 else 0

                    # Idempotent billing: only bill if credits_used is still 0
                    bill_result = await db.execute(
                        update(Meeting)
                        .where(Meeting.id == m.id, Meeting.credits_used == 0)
                        .values(
                            status="ended",
                            ended_at=now,
                            duration_minutes=minutes_used,
                            credits_used=minutes_used,
                        )
                    )

                    if bill_result.rowcount == 1 and minutes_used > 0:
                        # Settle against the 5-min reserve
                        delta = minutes_used - 5
                        await db.execute(
                            update(User)
                            .where(User.id == m.user_id)
                            .values(credits=User.credits - delta)
                        )
                        logger.info("Orphan billing: meeting %s charged %d min (delta %d)", m.id, minutes_used, delta)
                    else:
                        # Already billed or no duration — just ensure terminal state
                        m.status = "ended"
                        if not m.ended_at:
                            m.ended_at = now

                    logger.info("Reconciled orphaned meeting %s to ended state", m.id)
            finally:
                await recall.close()

            await db.commit()
    except Exception as exc:
        logger.error("Orphaned bot cleanup failed: %s", exc)


async def _cleanup_stale_bots():
    """Background task that checks every 5 minutes for stale bots (> 2 hours) and kills them."""
    import math
    from datetime import datetime, timezone
    from sqlalchemy import select, update
    while True:
        try:
            await asyncio.sleep(300)  # every 5 minutes
            from app.api.routes.webhook import get_bot_engine
            from app.models.database import Meeting, User, AsyncSessionLocal
            from app.meeting.recall_client import RecallClient

            bot_engine = get_bot_engine()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            stale_ids = []

            # Checkpoint active sessions to DB for crash recovery
            try:
                import json as _json
                async with AsyncSessionLocal() as ckpt_db:
                    has_updates = False
                    for sid, session in list(bot_engine.sessions.items()):
                        if session.is_active and session.bot_id:
                            checkpoint = session.context_manager.get_checkpoint_state()
                            await ckpt_db.execute(
                                update(Meeting)
                                .where(Meeting.bot_id == session.bot_id)
                                .values(context_checkpoint=_json.dumps(checkpoint, default=str))
                            )
                            has_updates = True
                    if has_updates:
                        await ckpt_db.commit()
            except Exception as ckpt_exc:
                logger.debug("Context checkpoint save failed: %s", ckpt_exc)

            for sid, session in list(bot_engine.sessions.items()):
                if session.get_duration() > 7200:  # 2 hours
                    stale_ids.append(sid)

            for sid in stale_ids:
                try:
                    await bot_engine.stop_meeting(sid)
                    logger.info("Stale bot cleanup: stopped session %s (> 2 hours)", sid[:8])
                except Exception as exc:
                    logger.warning("Stale bot cleanup failed for session %s: %s", sid[:8], exc)

            # Also check database for meetings stuck as "active" > 2 hours
            async with AsyncSessionLocal() as db:
                from datetime import timedelta
                cutoff = now - timedelta(hours=2)
                result = await db.execute(
                    select(Meeting).where(
                        Meeting.status == "active",
                        Meeting.started_at.isnot(None),
                        Meeting.started_at < cutoff,
                    )
                )
                stale_meetings = result.scalars().all()
                for m in stale_meetings:
                    duration_seconds = (now - m.started_at).total_seconds()
                    minutes_used = max(1, math.ceil(duration_seconds / 60))

                    # Idempotent billing: only bill if credits_used is still 0
                    bill_result = await db.execute(
                        update(Meeting)
                        .where(Meeting.id == m.id, Meeting.credits_used == 0)
                        .values(
                            status="ended",
                            ended_at=now,
                            duration_minutes=minutes_used,
                            credits_used=minutes_used,
                        )
                    )

                    if bill_result.rowcount == 1:
                        # Settle against the 5-min reserve
                        delta = minutes_used - 5
                        await db.execute(
                            update(User)
                            .where(User.id == m.user_id)
                            .values(credits=User.credits - delta)
                        )
                    else:
                        # Already billed -- just ensure status is ended
                        m.status = "ended"
                        if not m.ended_at:
                            m.ended_at = now

                    # Try to stop the Recall bot
                    if m.bot_id:
                        try:
                            recall = RecallClient()
                            await recall.stop_bot(m.bot_id)
                            await recall.close()
                        except Exception:
                            pass

                    logger.info("Stale meeting cleanup: ended meeting %s (%d min)", m.id, minutes_used)

                if stale_meetings:
                    await db.commit()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Stale bot cleanup error: %s", exc)


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
app.include_router(bot.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
app.include_router(live.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(webhook.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(usage.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(ws_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "synth-api"}


@app.get("/api/health/meeting-latency")
async def meeting_latency_metrics():
    """Rolling p50/p95 for meeting Q&A stage deltas (in-process only)."""
    settings = get_settings()
    if settings.environment != "development" and not settings.expose_meeting_latency_metrics:
        raise HTTPException(status_code=404, detail="Not found")
    from app.observability.meeting_latency_store import snapshot_percentiles

    return snapshot_percentiles()
