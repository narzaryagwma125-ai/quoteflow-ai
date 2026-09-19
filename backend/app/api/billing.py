from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_origin
from app.core.errors import bad_request
from app.db.session import get_db
from app.models.user import User
from app.payments.stripe import (
    cancel_subscription_at_period_end,
    create_checkout_session,
)
from app.schemas.billing import (
    CancelSubscriptionResponse,
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionPublic,
)
from app.security.rate_limit import client_ip_key, enforce
from app.services.audit import audit
from app.services.subscription import get_subscription, get_usage_summary

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    verify_origin(request)
    await enforce(client_ip_key(request), "stripe_checkout", limit=15, window_seconds=3600)

    # Validate the internal plan; never accept price IDs from the frontend.
    if payload.plan not in ("starter", "business"):
        raise bad_request("Invalid plan selected.")

    try:
        session = create_checkout_session(
            user_id=user.id,
            email=user.email,
            plan=payload.plan,
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except stripe.error.StripeError:
        await audit(db, "stripe.checkout_error", user_id=user.id)
        await db.commit()
        raise bad_request("Unable to create a checkout session. Please try again.") from None

    await audit(db, "stripe.checkout_created", user_id=user.id, entity_type="billing")
    await db.commit()
    return CheckoutResponse(url=session["url"])


@router.get("/subscription", response_model=SubscriptionPublic)
async def subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPublic:
    summary = await get_usage_summary(db, user)
    return SubscriptionPublic(
        plan=summary["plan"],
        status=summary["subscription_status"],
        current_period_start=summary["current_period_start"],
        current_period_end=summary["current_period_end"],
        cancel_at_period_end=summary["cancel_at_period_end"],
        quotes_used=summary["quotes_used"],
        quotes_limit=summary["quotes_limit"],
        quotes_remaining=summary["quotes_remaining"],
        ai_used=summary["ai_used"],
        ai_limit=summary["ai_limit"],
        ai_remaining=summary["ai_remaining"],
        trial_active=summary["trial_active"],
        trial_expired=summary["trial_expired"],
        trial_days_remaining=summary["trial_days_remaining"],
        trial_expires_at=summary["trial_expires_at"],
        trial_unlimited=summary["trial_unlimited"],
    )


@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CancelSubscriptionResponse:
    verify_origin(request)
    sub = await get_subscription(db, user.id)
    if sub is None or sub.status not in ("active", "trialing", "past_due"):
        raise bad_request("No active subscription to cancel.")

    if sub.provider_subscription_id:
        try:
            cancel_subscription_at_period_end(sub.provider_subscription_id)
        except stripe.error.StripeError:
            raise bad_request("Unable to cancel the subscription. Please contact support.") from None

    sub.cancel_at_period_end = True
    await audit(db, "billing.cancel_requested", user_id=user.id, entity_type="billing")
    await db.commit()
    await db.refresh(sub)
    return CancelSubscriptionResponse(
        plan=sub.plan, status=sub.status, cancel_at_period_end=True
    )
