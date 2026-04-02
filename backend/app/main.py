from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.database import engine, Base
from app.models.credit_transaction import CreditTransaction  # noqa: F401 — register model
from app.api.routes import auth, agents, meetings, documents, payments, credits
from app.api.websocket import router as ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
app.include_router(meetings.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(ws_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "synth-api"}
