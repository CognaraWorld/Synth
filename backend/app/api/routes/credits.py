"""Credit management endpoints: balance, transaction history, and refunds."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.models.credit_transaction import CreditTransaction
from app.models.database import Meeting, User, get_db
from app.models.schemas import (
    CreditBalanceResponse,
    CreditTransactionListResponse,
    CreditTransactionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's current credit balance."""
    return CreditBalanceResponse(
        credits=current_user.credits,
        user_id=current_user.id,
    )


@router.get("/transactions", response_model=CreditTransactionListResponse)
async def list_transactions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a paginated list of the user's credit transactions."""
    offset = (page - 1) * per_page

    count_result = await db.execute(
        select(func.count(CreditTransaction.id)).where(
            CreditTransaction.user_id == current_user.id
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    transactions = result.scalars().all()

    return CreditTransactionListResponse(
        transactions=[CreditTransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/refund/{meeting_id}", response_model=CreditTransactionResponse)
async def refund_meeting_credit(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refund a credit for a failed meeting.

    Only meetings with status 'failed' are eligible for a refund.
    Each meeting can only be refunded once.
    """
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.user_id == current_user.id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    if meeting.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed meetings are eligible for a credit refund",
        )

    # Check if already refunded
    existing_refund = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.user_id == current_user.id,
            CreditTransaction.transaction_type == "refund",
            or_(
                CreditTransaction.meeting_id == meeting_id,
                CreditTransaction.description.contains(str(meeting_id)),
            ),
        )
    )
    if existing_refund.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This meeting has already been refunded",
        )

    credits_to_refund = meeting.credits_used

    # Atomic credit update: use SQL-level arithmetic to prevent race
    # conditions from concurrent requests (OWASP A04:2021 - Insecure Design).
    # The UPDATE happens in a single SQL statement, so no read-modify-write gap.
    result = await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(credits=User.credits + credits_to_refund)
        .returning(User.credits)
    )
    new_balance = result.scalar_one()

    transaction = CreditTransaction(
        user_id=current_user.id,
        meeting_id=meeting.id,
        amount=credits_to_refund,
        balance_after=new_balance,
        transaction_type="refund",
        description=f"Refund for failed meeting {meeting_id}",
    )
    db.add(transaction)

    await db.commit()
    await db.refresh(transaction)

    logger.info(
        "Refunded %d credit(s) to user %s for meeting %s",
        credits_to_refund,
        current_user.id,
        meeting_id,
    )

    return transaction
