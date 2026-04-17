"""Credit transaction model for tracking all credit movements."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.database import Base, _utcnow


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        Index(
            "ux_credit_transactions_refund_meeting_id",
            "meeting_id",
            unique=True,
            postgresql_where=text(
                "transaction_type = 'refund' AND meeting_id IS NOT NULL"
            ),
            sqlite_where=text(
                "transaction_type = 'refund' AND meeting_id IS NOT NULL"
            ),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=True)
    amount = Column(Integer, nullable=False)  # positive = added, negative = used
    balance_after = Column(Integer, nullable=False)
    transaction_type = Column(
        String(50), nullable=False
    )  # "purchase", "meeting_used", "refund", "free_credit"
    description = Column(String(500), nullable=False)
    stripe_session_id = Column(String(255), nullable=True, unique=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="credit_transactions")
    meeting = relationship("Meeting")
