from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_origin
from app.core.errors import bad_request
from app.db.session import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.payments.stripe import (
    cancel_subscription_at_period_end,
    create_checkout_session,
    get_stripe_client,
    plan_from_price_id,
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
    if payload.plan not in ("starter", "pro", "business"):
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


@router.post("/sync-stripe-subscriptions")
async def sync_stripe_subscriptions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reconcile this user's local Stripe rows with Stripe's current state.

    This is intentionally authenticated and rate-limited. It repairs historical
    webhook-ordering gaps without creating a new checkout or charging the user.
    """
    verify_origin(request)
    await enforce(
        client_ip_key(request),
        "stripe_subscription_sync",
        limit=3,
        window_seconds=3600,
    )

    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.provider == "stripe")
        .order_by(Subscription.id.desc())
    )
    subscriptions = result.scalars().all()
    synced = []
    errors = []

    # Ensure the Stripe SDK is initialized with the production secret key.
    # Checkout/webhook paths already do this; reconciliation must do it too.
    get_stripe_client()

    for sub in subscriptions:
        if not sub.provider_subscription_id:
            continue
        try:
            remote = stripe.Subscription.retrieve(sub.provider_subscription_id)
            remote_status = remote.get("status") if isinstance(remote, dict) else getattr(remote, "status", None)
            remote_customer = remote.get("customer") if isinstance(remote, dict) else getattr(remote, "customer", None)
            remote_items = (remote.get("items") if isinstance(remote, dict) else getattr(remote, "items", None)) or {}
            remote_data = remote_items.get("data", []) if isinstance(remote_items, dict) else getattr(remote_items, "data", []) or []
            price_id = ""
            if remote_data:
                first_item = remote_data[0]
                price = first_item.get("price", {}) if isinstance(first_item, dict) else getattr(first_item, "price", {})
                price_id = price.get("id", "") if isinstance(price, dict) else getattr(price, "id", "")
            remote_plan = plan_from_price_id(price_id)

            if remote_status:
                sub.status = remote_status
            if remote_customer:
                sub.provider_customer_id = remote_customer
            if remote_plan:
                sub.plan = remote_plan

            current_period_start = remote.get("current_period_start") if isinstance(remote, dict) else getattr(remote, "current_period_start", None)
            current_period_end = remote.get("current_period_end") if isinstance(remote, dict) else getattr(remote, "current_period_end", None)
            if current_period_start:
                from datetime import UTC, datetime
                sub.current_period_start = datetime.fromtimestamp(int(current_period_start), tz=UTC)
            if current_period_end:
                from datetime import UTC, datetime
                sub.current_period_end = datetime.fromtimestamp(int(current_period_end), tz=UTC)
            cancel_at_period_end = remote.get("cancel_at_period_end") if isinstance(remote, dict) else getattr(remote, "cancel_at_period_end", None)
            if cancel_at_period_end is not None:
                sub.cancel_at_period_end = bool(cancel_at_period_end)

            synced.append({
                "id": sub.id,
                "provider_subscription_id": sub.provider_subscription_id,
                "plan": sub.plan,
                "status": sub.status,
            })
        except stripe.error.StripeError as exc:
            errors.append({
                "provider_subscription_id": sub.provider_subscription_id,
                "error": str(exc),
            })

    await db.commit()
    return {
        "status": "synced",
        "synced": synced,
        "errors": errors,
    }


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
