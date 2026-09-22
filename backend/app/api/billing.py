from __future__ import annotations
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, verify_origin
from app.core.config import settings
from app.core.errors import bad_request
from app.db.session import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.payments.razorpay import cancel_subscription, create_subscription, fetch_subscription, verify_checkout_signature
from app.schemas.billing import CancelSubscriptionResponse, CheckoutRequest, CheckoutResponse, PaymentVerifyRequest, SubscriptionPublic
from app.security.rate_limit import client_ip_key, enforce
from app.services.audit import audit
from app.services.subscription import get_subscription, get_usage_summary

router = APIRouter(prefix="/api/billing", tags=["billing"])

@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(payload: CheckoutRequest, request: Request, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)) -> CheckoutResponse:
    verify_origin(request)
    await enforce(client_ip_key(request), "razorpay_checkout", limit=15, window_seconds=3600)
    try:
        data = create_subscription(user.id, user.email, payload.plan)
    except (ValueError, RuntimeError) as exc:
        raise bad_request(str(exc)) from exc
    sub = Subscription(user_id=user.id, provider="razorpay", provider_customer_id="",
                       provider_subscription_id=data["id"], plan=payload.plan, status="incomplete")
    db.add(sub)
    await audit(db, "razorpay.checkout_created", user_id=user.id, entity_type="billing")
    await db.commit()
    return CheckoutResponse(key_id=settings.razorpay_key_id, subscription_id=data["id"],
                             prefill_email=user.email)

@router.post("/verify")
async def verify_payment(payload: PaymentVerifyRequest, request: Request,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)) -> dict:
    verify_origin(request)
    await enforce(client_ip_key(request), "razorpay_verify", limit=10, window_seconds=3600)
    result = await db.execute(select(Subscription).where(
        Subscription.user_id == user.id, Subscription.provider == "razorpay",
        Subscription.provider_subscription_id == payload.razorpay_subscription_id))
    sub = result.scalar_one_or_none()
    if sub is None:
        raise bad_request("Subscription was not created for this account.")
    if not verify_checkout_signature(payload.razorpay_subscription_id, payload.razorpay_payment_id,
                                     payload.razorpay_signature):
        raise bad_request("Invalid Razorpay payment signature.")
    try:
        remote = fetch_subscription(payload.razorpay_subscription_id)
    except RuntimeError as exc:
        raise bad_request("Payment received, but subscription status could not be confirmed yet.") from exc
    status = remote.get("status", "")
    if status in {"authenticated", "active"}:
        sub.status = "active"
    start_at, end_at = remote.get("current_start"), remote.get("current_end")
    if start_at: sub.current_period_start = datetime.fromtimestamp(int(start_at), tz=UTC)
    if end_at: sub.current_period_end = datetime.fromtimestamp(int(end_at), tz=UTC)
    sub.provider_customer_id = str(remote.get("customer_id") or remote.get("customer") or "")
    await audit(db, "razorpay.payment_verified", user_id=user.id, entity_type="billing")
    await db.commit()
    return {"status": "verified", "subscription_status": sub.status}

@router.get("/subscription", response_model=SubscriptionPublic)
async def subscription(user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)) -> SubscriptionPublic:
    summary = await get_usage_summary(db, user)
    return SubscriptionPublic(**{k: summary[k] for k in SubscriptionPublic.model_fields})

@router.post("/sync-razorpay-subscriptions")
async def sync_razorpay_subscriptions(request: Request, user: User = Depends(get_current_user),
                                      db: AsyncSession = Depends(get_db)) -> dict:
    verify_origin(request)
    await enforce(client_ip_key(request), "razorpay_subscription_sync", limit=3, window_seconds=3600)
    result = await db.execute(select(Subscription).where(
        Subscription.user_id == user.id, Subscription.provider == "razorpay").order_by(Subscription.id.desc()))
    synced, errors = [], []
    for sub in result.scalars().all():
        if not sub.provider_subscription_id: continue
        try:
            remote = fetch_subscription(sub.provider_subscription_id)
            if remote.get("status"): sub.status = remote["status"]
            if remote.get("current_start"): sub.current_period_start = datetime.fromtimestamp(int(remote["current_start"]), tz=UTC)
            if remote.get("current_end"): sub.current_period_end = datetime.fromtimestamp(int(remote["current_end"]), tz=UTC)
            synced.append({"id": sub.id, "provider_subscription_id": sub.provider_subscription_id,
                            "plan": sub.plan, "status": sub.status})
        except RuntimeError as exc:
            errors.append({"provider_subscription_id": sub.provider_subscription_id, "error": str(exc)})
    await db.commit()
    return {"status": "synced", "synced": synced, "errors": errors}

@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel(request: Request, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)) -> CancelSubscriptionResponse:
    verify_origin(request)
    sub = await get_subscription(db, user.id)
    if sub is None or sub.provider != "razorpay" or sub.status not in ("active", "trialing", "past_due"):
        raise bad_request("No active subscription to cancel.")
    if sub.provider_subscription_id:
        try: cancel_subscription(sub.provider_subscription_id)
        except RuntimeError: raise bad_request("Unable to cancel the subscription. Please contact support.") from None
    sub.cancel_at_period_end = True
    await audit(db, "billing.cancel_requested", user_id=user.id, entity_type="billing")
    await db.commit(); await db.refresh(sub)
    return CancelSubscriptionResponse(plan=sub.plan, status=sub.status, cancel_at_period_end=True)
