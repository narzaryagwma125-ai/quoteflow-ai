"""Stripe webhook endpoint. Signature-verified, idempotent, out-of-order safe."""

from __future__ import annotations

from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request
from app.db.session import get_db
from app.models.payment_event import PaymentEvent
from app.models.subscription import Subscription
from app.payments.stripe import plan_from_price_id, payload_hash, verify_webhook_signature
from app.services.audit import audit

router = APIRouter(tags=["webhooks"])

SUBSCRIPTION_EVENTS = (
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
)
INVOICE_EVENTS = ("invoice.paid", "invoice.payment_failed")


async def _record_event(db: AsyncSession, event: stripe.Event, raw_body: bytes) -> bool:
    """Idempotently record a webhook event. Returns True if already processed."""
    stmt = pg_insert(PaymentEvent).values(
        provider="stripe",
        provider_event_id=event["id"],
        event_type=event["type"],
        processed_at=datetime.now(UTC),
        payload_hash=payload_hash(raw_body),
    ).on_conflict_do_nothing(
        index_elements=[PaymentEvent.provider, PaymentEvent.provider_event_id]
    ).returning(PaymentEvent.id)
    result = await db.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    if inserted_id is None:
        return True
    return False


def _to_dt(ts) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=UTC)



async def _find_subscription(db: AsyncSession, sub_id: str, customer_id: str) -> Subscription | None:
    if sub_id:
        result = await db.execute(
            select(Subscription).where(Subscription.provider_subscription_id == sub_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            return sub
    if customer_id:
        result = await db.execute(
            select(Subscription).where(Subscription.provider_customer_id == customer_id)
        )
        sub = result.scalar_one_or_none()
        if sub and sub_id and not sub.provider_subscription_id:
            sub.provider_subscription_id = sub_id
            await db.flush()
        return sub
    return None


async def _upsert_subscription(
    db: AsyncSession,
    *,
    user_id: int,
    customer_id: str | None,
    sub_id: str | None,
    plan: str = "free",
    status: str = "incomplete",
) -> Subscription:
    """Atomically create/update a Stripe subscription by its unique Stripe ID."""
    if not sub_id:
        raise ValueError("Stripe subscription ID is required.")

    values = {
        "user_id": user_id,
        "provider": "stripe",
        "provider_customer_id": customer_id,
        "provider_subscription_id": sub_id,
        "plan": plan,
        "status": status,
    }
    stmt = pg_insert(Subscription).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Subscription.provider_subscription_id],
        set_={
            "user_id": stmt.excluded.user_id,
            "provider_customer_id": stmt.excluded.provider_customer_id,
            "updated_at": datetime.now(UTC),
        },
    ).returning(Subscription.id)
    result = await db.execute(stmt)
    sub_id_db = result.scalar_one()
    sub = await db.get(Subscription, sub_id_db)
    if sub is None:
        raise RuntimeError("Stripe subscription upsert succeeded but row could not be loaded.")
    return sub


async def _handle_event(db: AsyncSession, event: stripe.Event) -> None:
    etype = event["type"]
    data = event["data"]["object"]

    if etype == "checkout.session.completed":
        meta = data.get("metadata") or {}
        user_id = meta.get("quoteflow_user_id")
        customer_id = data.get("customer")
        sub_id = (data.get("subscription") or "").strip()
        if user_id and customer_id and sub_id:
            sub = await _upsert_subscription(
                db, user_id=int(user_id), customer_id=customer_id, sub_id=sub_id
            )
            await db.flush()

    elif etype in SUBSCRIPTION_EVENTS:
        sub_id = (data.get("id") or "").strip()
        customer_id = data.get("customer", "")
        metadata = data.get("metadata") or {}
        user_id = metadata.get("quoteflow_user_id")
        sub = await _find_subscription(db, sub_id, customer_id)

        # If checkout.session.completed has not created the row yet, Stripe
        # subscription metadata lets us create it atomically.
        if sub is None and user_id and customer_id and sub_id:
            sub = await _upsert_subscription(
                db,
                user_id=int(user_id),
                customer_id=customer_id,
                sub_id=sub_id,
                status=data.get("status", "incomplete"),
            )

        if sub is None:
            return

        plan = plan_from_price_id(
            data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
        )
        if plan:
            sub.plan = plan
        sub.status = data.get("status", sub.status)

        # Stripe webhooks can arrive out of order. If this event still says
        # `incomplete`, check Stripe's current subscription state before
        # persisting it. This recovers the case where invoice.paid was
        # delivered before customer.subscription.created/updated.
        if sub.status == "incomplete":
            try:
                remote_sub = stripe.Subscription.retrieve(sub_id)
                remote_status = remote_sub.get("status") if isinstance(remote_sub, dict) else getattr(remote_sub, "status", None)
                if remote_status:
                    sub.status = remote_status
                remote_items = (remote_sub.get("items") if isinstance(remote_sub, dict) else getattr(remote_sub, "items", None)) or {}
                remote_data = remote_items.get("data", []) if isinstance(remote_items, dict) else getattr(remote_items, "data", []) or []
                if remote_data:
                    remote_price = remote_data[0].get("price", {}) if isinstance(remote_data[0], dict) else getattr(remote_data[0], "price", {})
                    remote_price_id = remote_price.get("id", "") if isinstance(remote_price, dict) else getattr(remote_price, "id", "")
                    remote_plan = plan_from_price_id(remote_price_id)
                    if remote_plan:
                        sub.plan = remote_plan
            except stripe.error.StripeError:
                # Keep the webhook payload as the safe fallback; a later
                # Stripe event or the reconciliation endpoint can retry.
                pass

        sub.current_period_start = _to_dt(data.get("current_period_start"))
        sub.current_period_end = _to_dt(data.get("current_period_end"))
        sub.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
        sub.provider_customer_id = customer_id or sub.provider_customer_id
        if etype == "customer.subscription.deleted":
            sub.status = "canceled"
            sub.cancel_at_period_end = True
        await db.flush()

    elif etype in INVOICE_EVENTS:
        customer_id = data.get("customer", "")
        stripe_sub_id = (data.get("subscription") or "").strip()
        sub = await _find_subscription(db, stripe_sub_id, customer_id)
        if sub is not None:
            if etype == "invoice.paid":
                # invoice.paid is the authoritative signal that the first
                # subscription payment succeeded.  Stripe can deliver this
                # before/after customer.subscription.updated, so do not leave
                # a paid subscription stuck at `incomplete`.
                sub.status = "active"
                # Also recover the plan from the invoice price. This makes the
                # webhook path resilient when subscription.updated was missed
                # or arrived before the price metadata was available.
                lines = (data.get("lines") or {}).get("data") or []
                for line in lines:
                    price = (line.get("price") or {}) if isinstance(line, dict) else {}
                    plan = plan_from_price_id(price.get("id", ""))
                    if plan:
                        sub.plan = plan
                        break
            elif etype == "invoice.payment_failed":
                sub.status = "past_due"
            await db.flush()

    await audit(db, f"stripe.webhook:{etype}", entity_type="billing", entity_id=event["id"])
    await db.commit()


@router.post("/api/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not signature:
        raise bad_request("Missing Stripe signature.")

    try:
        event = verify_webhook_signature(raw_body, signature)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise bad_request("Invalid Stripe signature.") from None

    event_id = event["id"]
    if await _record_event(db, event, raw_body):
        # Already processed — return 200 idempotently.
        return {"status": "duplicate", "event_id": event_id}

    await _handle_event(db, event)
    return {"status": "processed", "event_id": event_id}
