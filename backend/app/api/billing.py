from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_origin
from app.core.config import settings
from app.core.errors import bad_request
from app.db.session import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.payments.paypal import (
    capture_order,
    create_order,
    get_order,
    plan_price_usd,
    validate_captured_order,
)
from app.payments.razorpay import (
    cancel_subscription,
    create_subscription,
    fetch_subscription,
    verify_checkout_signature,
)
from app.schemas.billing import (
    CancelSubscriptionResponse,
    CheckoutRequest,
    CheckoutResponse,
    PayPalCaptureRequest,
    PaymentVerifyRequest,
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

    if payload.provider == "razorpay":
        await enforce(client_ip_key(request), "razorpay_checkout", limit=15, window_seconds=3600)
        try:
            data = create_subscription(user.id, user.email, payload.plan)
        except (ValueError, RuntimeError) as exc:
            raise bad_request(str(exc)) from exc

        sub = Subscription(
            user_id=user.id,
            provider="razorpay",
            provider_customer_id="",
            provider_subscription_id=data["id"],
            provider_reference_id=None,
            plan=payload.plan,
            status="incomplete",
        )
        db.add(sub)
        await audit(db, "razorpay.checkout_created", user_id=user.id, entity_type="billing")
        await db.commit()

        return CheckoutResponse(
            provider="razorpay",
            key_id=settings.razorpay_key_id,
            subscription_id=data["id"],
            name="QuoteFlow AI",
            description="QuoteFlow AI subscription",
            prefill_email=user.email,
        )

    await enforce(client_ip_key(request), "paypal_checkout", limit=15, window_seconds=3600)
    try:
        data = create_order(user_id=user.id, plan=payload.plan)
    except (ValueError, RuntimeError) as exc:
        raise bad_request(str(exc)) from exc

    order_id = str(data.get("id") or "")
    if not order_id:
        raise bad_request("PayPal did not return an order ID.")

    sub = Subscription(
        user_id=user.id,
        provider="paypal",
        provider_customer_id="",
        provider_subscription_id=None,
        provider_reference_id=order_id,
        plan=payload.plan,
        status="incomplete",
    )
    db.add(sub)
    await audit(db, "paypal.order_created", user_id=user.id, entity_type="billing")
    await db.commit()

    return CheckoutResponse(
        provider="paypal",
        order_id=order_id,
        paypal_client_id=settings.paypal_client_id,
        currency="USD",
        amount=f"{plan_price_usd(payload.plan):.2f}",
        name="QuoteFlow AI",
        description=f"QuoteFlow AI {payload.plan.title()} - 30 days",
        prefill_email=user.email,
    )


@router.post("/verify")
async def verify_payment(
    payload: PaymentVerifyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    verify_origin(request)
    await enforce(client_ip_key(request), "razorpay_verify", limit=10, window_seconds=3600)

    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.provider == "razorpay",
            Subscription.provider_subscription_id == payload.razorpay_subscription_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise bad_request("Subscription was not created for this account.")

    if not verify_checkout_signature(
        payload.razorpay_subscription_id,
        payload.razorpay_payment_id,
        payload.razorpay_signature,
    ):
        raise bad_request("Invalid Razorpay payment signature.")

    try:
        remote = fetch_subscription(payload.razorpay_subscription_id)
    except RuntimeError as exc:
        raise bad_request(
            "Payment received, but subscription status could not be confirmed yet."
        ) from exc

    status = remote.get("status", "")
    if status in {"authenticated", "active"}:
        sub.status = "active"

    start_at, end_at = remote.get("current_start"), remote.get("current_end")
    if start_at:
        sub.current_period_start = datetime.fromtimestamp(int(start_at), tz=UTC)
    if end_at:
        sub.current_period_end = datetime.fromtimestamp(int(end_at), tz=UTC)

    sub.provider_customer_id = str(
        remote.get("customer_id") or remote.get("customer") or ""
    )
    await audit(db, "razorpay.payment_verified", user_id=user.id, entity_type="billing")
    await db.commit()
    return {"status": "verified", "subscription_status": sub.status}


@router.post("/paypal/capture")
async def capture_paypal(
    payload: PayPalCaptureRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    verify_origin(request)
    await enforce(client_ip_key(request), "paypal_capture", limit=10, window_seconds=3600)

    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.provider == "paypal",
            Subscription.provider_reference_id == payload.order_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise bad_request("PayPal order was not created for this account.")

    if sub.status == "active" and sub.current_period_end:
        return {"status": "already_captured", "subscription_status": sub.status}

    try:
        captured = capture_order(payload.order_id)
    except (ValueError, RuntimeError) as exc:
        # If the browser retried after a successful capture, retrieve the order
        # before reporting a failure.
        try:
            captured = get_order(payload.order_id)
        except (ValueError, RuntimeError):
            raise bad_request(str(exc)) from exc

    ok, reason = validate_captured_order(
        captured,
        user_id=user.id,
        plan=sub.plan,
    )
    if not ok:
        raise bad_request(reason)

    sub.status = "active"
    sub.current_period_start = datetime.now(UTC)
    sub.current_period_end = datetime.now(UTC) + timedelta(days=30)
    await audit(db, "paypal.payment_captured", user_id=user.id, entity_type="billing")
    await db.commit()

    return {
        "status": "captured",
        "subscription_status": sub.status,
        "current_period_end": sub.current_period_end.isoformat(),
    }


@router.get("/subscription", response_model=SubscriptionPublic)
async def subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPublic:
    summary = await get_usage_summary(db, user)
    return SubscriptionPublic(
        **{k: summary[k] for k in SubscriptionPublic.model_fields}
    )


@router.post("/sync-razorpay-subscriptions")
async def sync_razorpay_subscriptions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    verify_origin(request)
    await enforce(
        client_ip_key(request),
        "razorpay_subscription_sync",
        limit=3,
        window_seconds=3600,
    )
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.provider == "razorpay",
        )
        .order_by(Subscription.id.desc())
    )
    synced, errors = [], []
    for sub in result.scalars().all():
        if not sub.provider_subscription_id:
            continue
        try:
            remote = fetch_subscription(sub.provider_subscription_id)
            if remote.get("status"):
                sub.status = remote["status"]
            if remote.get("current_start"):
                sub.current_period_start = datetime.fromtimestamp(
                    int(remote["current_start"]), tz=UTC
                )
            if remote.get("current_end"):
                sub.current_period_end = datetime.fromtimestamp(
                    int(remote["current_end"]), tz=UTC
                )
            synced.append(
                {
                    "id": sub.id,
                    "provider_subscription_id": sub.provider_subscription_id,
                    "plan": sub.plan,
                    "status": sub.status,
                }
            )
        except RuntimeError as exc:
            errors.append(
                {
                    "provider_subscription_id": sub.provider_subscription_id,
                    "error": str(exc),
                }
            )
    await db.commit()
    return {"status": "synced", "synced": synced, "errors": errors}


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

    if sub.provider == "razorpay":
        if sub.provider_subscription_id:
            try:
                cancel_subscription(sub.provider_subscription_id)
            except RuntimeError:
                raise bad_request(
                    "Unable to cancel the Razorpay subscription. Please contact support."
                ) from None
        sub.cancel_at_period_end = True
        await audit(db, "razorpay.cancel_requested", user_id=user.id, entity_type="billing")
    elif sub.provider == "paypal":
        # PayPal Orders checkout is a one-time 30-day purchase, not an
        # auto-renewing subscription. There is therefore nothing to cancel
        # remotely; marking the local subscription prevents renewal/access
        # beyond the paid period.
        sub.cancel_at_period_end = True
        await audit(db, "paypal.renewal_not_requested", user_id=user.id, entity_type="billing")
    else:
        raise bad_request("Unsupported payment provider.")

    await db.commit()
    await db.refresh(sub)
    return CancelSubscriptionResponse(
        plan=sub.plan,
        status=sub.status,
        cancel_at_period_end=True,
    )
