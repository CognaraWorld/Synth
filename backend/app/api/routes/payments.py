"""Stripe payment integration for purchasing credit packs."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.config import get_settings
from app.models.credit_transaction import CreditTransaction
from app.models.database import User, get_db
from app.models.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    CreditTransactionListResponse,
    CreditTransactionResponse,
)

try:
    import stripe
except ModuleNotFoundError:  # pragma: no cover - depends on local optional install
    stripe = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()

CREDIT_PACKS: dict[str, dict[str, Any]] = {
    "pack_5": {"credits": 5, "price_cents": 3000, "label": "5 Credits"},
    "pack_20": {"credits": 20, "price_cents": 10000, "label": "20 Credits"},
    "pack_50": {"credits": 50, "price_cents": 20000, "label": "50 Credits"},
}


def _require_stripe_sdk() -> Any:
    if stripe is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service is unavailable because the Stripe SDK is not installed.",
        )
    return stripe


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for a credit pack purchase."""
    pack = CREDIT_PACKS.get(body.pack_id)
    if not pack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pack_id. Choose from: {', '.join(CREDIT_PACKS.keys())}",
        )

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service is not configured",
        )

    stripe_sdk = _require_stripe_sdk()
    stripe_error = getattr(stripe_sdk, "StripeError", Exception)
    stripe_sdk.api_key = settings.stripe_secret_key

    try:
        session = stripe_sdk.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": pack["price_cents"],
                        "product_data": {
                            "name": f"Synth - {pack['label']}",
                            "description": f"{pack['credits']} meeting credits for Synth AI",
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "user_id": str(current_user.id),
                "pack_id": body.pack_id,
            },
            success_url=settings.frontend_success_url,
            cancel_url=settings.frontend_cancel_url,
        )
    except stripe_error as exc:
        logger.error("Stripe checkout creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create checkout session",
        )

    return CheckoutResponse(checkout_url=session.url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events. Verifies signature and processes completed checkouts."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    stripe_sdk = _require_stripe_sdk()
    signature_error = getattr(
        getattr(stripe_sdk, "error", None),
        "SignatureVerificationError",
        Exception,
    )
    stripe_sdk.api_key = settings.stripe_secret_key

    try:
        event = stripe_sdk.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        logger.warning("Invalid webhook payload received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except signature_error:
        logger.warning("Webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        await _handle_checkout_completed(session_data, db)

    return {"status": "ok"}


async def _handle_checkout_completed(
    session_data: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Process a completed checkout session: add credits and record the transaction."""
    metadata = session_data.get("metadata", {})
    user_id = metadata.get("user_id")
    pack_id = metadata.get("pack_id")
    stripe_session_id = session_data.get("id")

    if not user_id or not pack_id:
        logger.error(
            "Webhook missing metadata. user_id=%s, pack_id=%s", user_id, pack_id
        )
        return

    pack = CREDIT_PACKS.get(pack_id)
    if not pack:
        logger.error("Webhook received unknown pack_id: %s", pack_id)
        return

    # Check for duplicate processing
    existing = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.stripe_session_id == stripe_session_id
        )
    )
    if existing.scalar_one_or_none():
        logger.info("Duplicate webhook for session %s, skipping", stripe_session_id)
        return

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.error("Webhook user not found: %s", user_id)
        return

    credits_to_add = pack["credits"]
    user.credits += credits_to_add
    new_balance = user.credits

    transaction = CreditTransaction(
        user_id=user.id,
        amount=credits_to_add,
        balance_after=new_balance,
        transaction_type="purchase",
        description=f"Purchased {pack['label']} ({pack_id})",
        stripe_session_id=stripe_session_id,
    )
    db.add(transaction)

    await db.commit()
    logger.info(
        "Added %d credits to user %s (balance: %d)",
        credits_to_add,
        user_id,
        new_balance,
    )


@router.get("/history", response_model=CreditTransactionListResponse)
async def payment_history(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's credit purchase history."""
    offset = (page - 1) * per_page

    # Count total purchase transactions
    count_result = await db.execute(
        select(func.count(CreditTransaction.id)).where(
            CreditTransaction.user_id == current_user.id,
            CreditTransaction.transaction_type == "purchase",
        )
    )
    total = count_result.scalar() or 0

    # Fetch paginated purchase transactions
    result = await db.execute(
        select(CreditTransaction)
        .where(
            CreditTransaction.user_id == current_user.id,
            CreditTransaction.transaction_type == "purchase",
        )
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
