"""Credit transaction model for tracking all credit movements."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.database import Base


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # positive = added, negative = used
    balance_after = Column(Integer, nullable=False)
    transaction_type = Column(
        String(50), nullable=False
    )  # "purchase", "meeting_used", "refund", "free_credit"
    description = Column(String(500), nullable=False)
    stripe_session_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="credit_transactions")
