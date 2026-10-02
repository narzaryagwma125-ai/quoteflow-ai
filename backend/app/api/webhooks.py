"""Payment-provider webhook endpoints with signature verification and idempotency."""

from __future__ import annotations

from datetime import UTC, datetime
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request
from app.db.session import get_db
from app.models.payment_event import PaymentEvent
from app.models.subscription import Subscription
from app.payments.paypal import (
    get_order,
    payload_hash as paypal_payload_hash,
    validate_captured_order,
    verify_webhook_signature as verify_paypal_webhook_signature,
)
from app.payments.razorpay import (
    payload_hash,
    plan_from_plan_id,
    verify_webhook_signature,
)
from app.services.audit import audit

router = APIRouter(tags=["webhooks"])


@router.post("/api/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not signature or not verify_webhook_signature(raw_body, signature):
        raise bad_request("Invalid Razorpay webhook signature.")

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        raise bad_request("Invalid webhook JSON.") from None

    event_id = request.headers.get("x-razorpay-event-id") or event.get("id", "")
    if not event_id:
        raise bad_request("Missing Razorpay event ID.")

    stmt = (
        pg_insert(PaymentEvent)
        .values(
            provider="razorpay",
            provider_event_id=event_id,
            event_type=event.get("event", ""),
            processed_at=datetime.now(UTC),
            payload_hash=payload_hash(raw_body),
        )
        .on_conflict_do_nothing(
            index_elements=[PaymentEvent.provider, PaymentEvent.provider_event_id]
        )
        .returning(PaymentEvent.id)
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        return {"status": "duplicate", "event_id": event_id}

    etype = event.get("event", "")
    payload = event.get("payload") or {}
    sub_data = ((payload.get("subscription") or {}).get("entity") or {})
    sub_id = sub_data.get("id", "")

    if sub_id:
        result = await db.execute(
            select(Subscription).where(
                Subscription.provider == "razorpay",
                Subscription.provider_subscription_id == sub_id,
            )
        )
        sub = result.scalar_one_or_none()
        notes = sub_data.get("notes") or {}

        if sub is None and notes.get("quoteflow_user_id"):
            sub = Subscription(
                user_id=int(notes["quoteflow_user_id"]),
                provider="razorpay",
                provider_customer_id=str(sub_data.get("customer_id") or ""),
                provider_subscription_id=sub_id,
                provider_reference_id=None,
                plan=notes.get("quoteflow_plan", "free"),
                status="incomplete",
            )
            db.add(sub)
            await db.flush()

        if sub:
            plan = notes.get("quoteflow_plan") or plan_from_plan_id(
                sub_data.get("plan_id")
            )
            if plan:
                sub.plan = plan
            sub.provider_customer_id = str(
                sub_data.get("customer_id") or sub.provider_customer_id or ""
            )

            if etype in {"subscription.activated", "subscription.charged"}:
                sub.status = "active"
            elif etype == "subscription.pending":
                sub.status = "past_due"
            elif etype in {
                "subscription.halted",
                "subscription.cancelled",
                "subscription.completed",
            }:
                sub.status = "canceled"
                sub.cancel_at_period_end = True

            if sub_data.get("current_start"):
                sub.current_period_start = datetime.fromtimestamp(
                    int(sub_data["current_start"]), tz=UTC
                )
            if sub_data.get("current_end"):
                sub.current_period_end = datetime.fromtimestamp(
                    int(sub_data["current_end"]), tz=UTC
                )

    await audit(
        db,
        f"razorpay.webhook:{etype}",
        entity_type="billing",
        entity_id=event_id,
    )
    await db.commit()
    return {"status": "processed", "event_id": event_id}


@router.post("/api/webhooks/paypal")
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw_body = await request.body()
    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        raise bad_request("Invalid PayPal webhook JSON.") from None

    event_id = str(event.get("id") or "")
    if not event_id:
        raise bad_request("Missing PayPal event ID.")

    verified = verify_paypal_webhook_signature(
        transmission_id=request.headers.get("paypal-transmission-id", ""),
        transmission_time=request.headers.get("paypal-transmission-time", ""),
        cert_url=request.headers.get("paypal-cert-url", ""),
        auth_algo=request.headers.get("paypal-auth-algo", ""),
        transmission_sig=request.headers.get("paypal-transmission-sig", ""),
        webhook_id=request.headers.get("paypal-webhook-id", ""),
        webhook_event=event,
    )
    if not verified:
        raise bad_request("Invalid PayPal webhook signature.")

    stmt = (
        pg_insert(PaymentEvent)
        .values(
            provider="paypal",
            provider_event_id=event_id,
            event_type=event.get("event_type", ""),
            processed_at=datetime.now(UTC),
            payload_hash=paypal_payload_hash(raw_body),
        )
        .on_conflict_do_nothing(
            index_elements=[PaymentEvent.provider, PaymentEvent.provider_event_id]
        )
        .returning(PaymentEvent.id)
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        return {"status": "duplicate", "event_id": event_id}

    event_type = str(event.get("event_type") or "")
    resource = event.get("resource") or {}
    order_id = str(
        ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get(
            "order_id"
        )
        or ""
    )

    if event_type in {"PAYMENT.CAPTURE.COMPLETED", "PAYMENT.SALE.COMPLETED"} and order_id:
        result = await db.execute(
            select(Subscription).where(
                Subscription.provider == "paypal",
                Subscription.provider_reference_id == order_id,
            )
        )
        sub = result.scalar_one_or_none()

        if sub is not None and sub.status != "active":
            try:
                order = get_order(order_id)
                ok, _ = validate_captured_order(
                    order, user_id=sub.user_id, plan=sub.plan
                )
            except (ValueError, RuntimeError):
                ok = False

            if ok:
                sub.status = "active"
                sub.current_period_start = datetime.now(UTC)
                # PayPal standard Orders are one-time purchases in this integration.
                from datetime import timedelta

                sub.current_period_end = datetime.now(UTC) + timedelta(days=30)

    await audit(
        db,
        f"paypal.webhook:{event_type}",
        entity_type="billing",
        entity_id=event_id,
    )
    await db.commit()
    return {"status": "processed", "event_id": event_id}
