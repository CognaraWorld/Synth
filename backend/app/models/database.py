import uuid
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings


class Base(DeclarativeBase):
    pass


DEFAULT_STARTER_CREDITS = 60  # minutes balance


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)  # null if OAuth only
    provider = Column(String(50), default="email")  # email, google
    credits = Column(Integer, default=DEFAULT_STARTER_CREDITS)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="user", cascade="all, delete-orphan")
    credit_transactions = relationship(
        "CreditTransaction", back_populates="user", cascade="all, delete-orphan"
    )
    usage_records = relationship(
        "UsageRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    operator_instructions = relationship(
        "OperatorInstruction",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False, default="Synth")
    description = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=False)
    mode = Column(Enum("general", "custom", name="agent_mode"), default="general")
    persona_id = Column(String(64), nullable=False, default="general")
    voice = Column(String(32), nullable=False, default="female")
    response_mode = Column(String(32), nullable=False, default="name_only")
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="agents")
    documents = relationship("Document", back_populates="agent", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="agent", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt
    file_size = Column(Integer, default=0)
    parsed = Column(Boolean, default=False)
    chunk_count = Column(Integer, default=0)
    doc_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    agent = relationship("Agent", back_populates="documents")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    platform = Column(Enum("zoom", "teams", "meet", name="meeting_platform"), nullable=False)
    meeting_link = Column(String(1024), nullable=False)
    status = Column(
        Enum("pending", "joining", "active", "ended", "failed", name="meeting_status"),
        default="pending",
    )
    bot_id = Column(String(255), nullable=True)  # Recall.ai bot ID
    transcript = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    credits_used = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="meetings")
    agent = relationship("Agent", back_populates="meetings")
    summary = relationship("MeetingSummary", back_populates="meeting", uselist=False)
    usage_record = relationship(
        "UsageRecord",
        back_populates="meeting",
        uselist=False,
    )
    live_session = relationship(
        "LiveSession",
        back_populates="meeting",
        uselist=False,
        cascade="all, delete-orphan",
    )
    operator_instructions = relationship(
        "OperatorInstruction",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    override = relationship("MeetingOverride", back_populates="meeting", uselist=False)


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    key_points = Column(Text, nullable=True)
    action_items = Column(Text, nullable=True)
    decisions = Column(Text, nullable=True)
    pdf_path = Column(String(1024), nullable=True)
    docx_path = Column(String(1024), nullable=True)
    email_delivery_status = Column(String(50), nullable=False, default="pending")
    email_delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    meeting = relationship("Meeting", back_populates="summary")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id"),
        unique=True,
        nullable=False,
    )
    minutes_used = Column(Float, nullable=False, default=0.0)
    recorded_at = Column(DateTime, nullable=False, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="usage_records")
    meeting = relationship("Meeting", back_populates="usage_record")


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), unique=True, nullable=False)
    engine_session_id = Column(String(64), nullable=True, unique=True)
    provider_bot_id = Column(String(255), nullable=True)
    session_status = Column(String(50), nullable=False, default="pending")
    is_muted = Column(Boolean, nullable=False, default=False)
    stop_requested = Column(Boolean, nullable=False, default=False)
    last_instruction_at = Column(DateTime, nullable=True)
    last_transcript_at = Column(DateTime, nullable=True)
    provider_last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    ended_at = Column(DateTime, nullable=True)

    meeting = relationship("Meeting", back_populates="live_session")
    instructions = relationship(
        "OperatorInstruction",
        back_populates="live_session",
        cascade="all, delete-orphan",
    )


class OperatorInstruction(Base):
    __tablename__ = "operator_instructions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    live_session_id = Column(UUID(as_uuid=True), ForeignKey("live_sessions.id"), nullable=True)
    instruction_text = Column(Text, nullable=False)
    delivery_status = Column(String(50), nullable=False, default="queued")
    delivery_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    applied_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="operator_instructions")
    meeting = relationship("Meeting", back_populates="operator_instructions")
    live_session = relationship("LiveSession", back_populates="instructions")


class MeetingOverride(Base):
    __tablename__ = "meeting_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    mode = Column(String(32), nullable=True)
    persona_id = Column(String(64), nullable=True)
    system_prompt = Column(Text, nullable=True)
    voice = Column(String(32), nullable=True)
    response_mode = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    meeting = relationship("Meeting", back_populates="override")


# Database engine setup
settings = get_settings()
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
