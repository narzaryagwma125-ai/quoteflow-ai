"""Billing & Stripe webhook tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.subscription import Subscription
from app.payments.stripe import payload_hash
from app.schemas.billing import CheckoutRequest as _cr  # noqa: F401
from tests.conftest import create_user, login


class FakeSession:
    def __init__(self, url="https://checkout.example/test"):
        self.id = "cs_test_123"
        self.url = url


def _fake_event(etype, event_id="evt_123", customer="cus_99", sub_id="sub_42", **data):
    obj = {
        "id": sub_id if etype.startswith("customer.subscription") else None,
        "object": "subscription" if etype.startswith("customer.subscription") else "checkout_session",
        "customer": customer,
        "status": "active",
        "current_period_start": int(datetime.now(UTC).timestamp()),
        "current_period_end": int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
        "cancel_at_period_end": False,
        "items": {"data": [{"price": {"id": "price_starter"}}]},
    }
    obj.update({k: v for k, v in data.items() if v is not None})
    return {"id": event_id, "type": etype, "data": {"object": obj}}


@pytest.mark.asyncio
async def test_checkout_requires_auth(client):
    res = await client.post("/api/billing/checkout", json={"plan": "starter"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_checkout_rejects_invalid_plan(client):
    await create_user("bill@example.com")
    await login(client, "bill@example.com")
    res = await client.post("/api/billing/checkout", json={"plan": "enterprise"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_checkout_returns_stripe_url(client, monkeypatch):
    await create_user("bill2@example.com")
    await login(client, "bill2@example.com")

    monkeypatch.setattr(
        "app.api.billing.create_checkout_session",
        lambda user_id, email, plan: {
            "id": "cs_ok",
            "url": "https://checkout.stripe.com/c/pay/cs_ok",
        },
    )
    res = await client.post("/api/billing/checkout", json={"plan": "starter"})
    assert res.status_code == 200, res.text
    assert "checkout.stripe.com" in res.json()["url"]


@pytest.mark.asyncio
async def test_subscription_summary_free_plan(client):
    # Backdate so the trial has expired: the plain free plan limits apply.
    await create_user(
        "bill3@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await login(client, "bill3@example.com")
    res = await client.get("/api/billing/subscription")
    assert res.status_code == 200
    body = res.json()
    assert body["plan"] == "free"
    assert body["trial_expired"] is True
    assert body["quotes_limit"] == 3
    assert body["quotes_remaining"] == 3


# --- Webhooks ---


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(client):
    res = await client.post(
        "/api/webhooks/stripe",
        content=b'{"id":"evt_bad","type":"x"}',
        headers={"stripe-signature": "t=1,v1=garbage"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_webhook_missing_signature(client):
    res = await client.post("/api/webhooks/stripe", content=b"{}")
    assert res.status_code == 400


def _signed_request(secret: str, payload: bytes, timestamp: int, scheme: str = "v1"):
    import hashlib
    import hmac

    signed_payload = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},{scheme}={signature}"


@pytest.mark.asyncio
async def test_webhook_signature_verified_and_subscription_upserted(client, monkeypatch):
    secret = "whsec_testsecret"
    import app.core.config as cfg

    monkeypatch.setattr(cfg.settings, "stripe_webhook_secret", secret)
    monkeypatch.setattr(
        cfg.settings, "stripe_starter_price_id", "price_starter"
    )
    monkeypatch.setattr(cfg.settings, "stripe_business_price_id", "price_business")

    user = await create_user("wh@example.com")
    async with async_session_factory() as db:
        db.add(
            Subscription(
                user_id=user.id,
                provider="stripe",
                provider_customer_id="cus_wh",
                provider_subscription_id="sub_wh",
                plan="starter",
                status="incomplete",
            )
        )
        await db.commit()

    event = _fake_event("customer.subscription.updated", sub_id="sub_wh", customer="cus_wh")
    payload = __import__("json").dumps(event).encode()
    signature_header = _signed_request(secret, payload, int(datetime.now(UTC).timestamp()))

    # verify payload actually includes the sub id (fake event correctly shaped)
    res = await client.post(
        "/api/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature_header, "content-type": "application/json"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "processed"

    async with async_session_factory() as db:
        sub = (await db.execute(select(Subscription).where(Subscription.provider_subscription_id == "sub_wh"))).scalar_one()
        assert sub.plan == "starter"
        assert sub.status == "active"
        assert sub.cancel_at_period_end is False


@pytest.mark.asyncio
async def test_duplicate_webhook_event_processed_once(client, monkeypatch):
    secret = "whsec_dup"
    from app.core.config import settings as cfg

    monkeypatch.setattr(cfg, "stripe_webhook_secret", secret)
    monkeypatch.setattr(cfg, "stripe_starter_price_id", "price_starter")
    monkeypatch.setattr(cfg, "stripe_business_price_id", "price_business")

    user = await create_user("whdup@example.com")
    async with async_session_factory() as db:
        db.add(
            Subscription(
                user_id=user.id,
                provider="stripe",
                provider_customer_id="cus_dup",
                provider_subscription_id="sub_dup",
                plan="starter",
                status="incomplete",
            )
        )
        await db.commit()

    event = _fake_event("customer.subscription.updated", event_id="evt_dup", sub_id="sub_dup", customer="cus_dup")
    payload = __import__("json").dumps(event).encode()
    headers = {
        "stripe-signature": _signed_request(secret, payload, int(datetime.now(UTC).timestamp())),
        "content-type": "application/json",
    }

    first = await client.post("/api/webhooks/stripe", content=payload, headers=headers)
    assert first.status_code == 200 and first.json()["status"] == "processed"
    second = await client.post("/api/webhooks/stripe", content=payload, headers=headers)
    assert second.status_code == 200 and second.json()["status"] == "duplicate"

    async with async_session_factory() as db:
        from app.models.payment_event import PaymentEvent

        rows = (await db.execute(select(PaymentEvent).where(PaymentEvent.provider_event_id == "evt_dup"))).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_checkout_session_completed_links_subscription(client, monkeypatch):
    secret = "whsec_link"
    from app.core.config import settings as cfg

    monkeypatch.setattr(cfg, "stripe_webhook_secret", secret)

    user = await create_user("whlink@example.com")
    event = _fake_event(
        "checkout.session.completed",
        event_id="evt_link",
        customer="cus_link",
        sub_id="sub_link",
    )
    obj = event["data"]["object"]
    obj["object"] = "checkout_session"
    obj["id"] = "cs_link"
    obj["subscription"] = "sub_link"
    obj["metadata"] = {"quoteflow_user_id": str(user.id)}

    payload = __import__("json").dumps(event).encode()
    headers = {
        "stripe-signature": _signed_request(secret, payload, int(datetime.now(UTC).timestamp())),
        "content-type": "application/json",
    }
    res = await client.post("/api/webhooks/stripe", content=payload, headers=headers)
    assert res.status_code == 200

    async with async_session_factory() as db:
        sub = (await db.execute(select(Subscription).where(Subscription.provider_subscription_id == "sub_link"))).scalar_one()
        assert sub.user_id == user.id
        assert sub.provider_customer_id == "cus_link"


@pytest.mark.asyncio
async def test_subscription_webhook_recovers_when_checkout_event_arrives_late(client, monkeypatch):
    secret = "whsec_out_of_order"
    from app.core.config import settings as cfg

    monkeypatch.setattr(cfg, "stripe_webhook_secret", secret)
    monkeypatch.setattr(cfg, "stripe_starter_price_id", "price_starter")
    monkeypatch.setattr(cfg, "stripe_business_price_id", "price_business")

    user = await create_user("whoutoforder@example.com")
    event = _fake_event(
        "customer.subscription.created",
        event_id="evt_out_of_order",
        customer="cus_out_of_order",
        sub_id="sub_out_of_order",
    )
    event["data"]["object"]["metadata"] = {"quoteflow_user_id": str(user.id)}

    payload = __import__("json").dumps(event).encode()
    headers = {
        "stripe-signature": _signed_request(secret, payload, int(datetime.now(UTC).timestamp())),
        "content-type": "application/json",
    }
    res = await client.post("/api/webhooks/stripe", content=payload, headers=headers)
    assert res.status_code == 200, res.text

    async with async_session_factory() as db:
        sub = (
            await db.execute(
                select(Subscription).where(
                    Subscription.provider_subscription_id == "sub_out_of_order"
                )
            )
        ).scalar_one()
        assert sub.user_id == user.id
        assert sub.provider_customer_id == "cus_out_of_order"
        assert sub.plan == "starter"
        assert sub.status == "active"


@pytest.mark.asyncio
async def test_invoice_payment_failed_sets_past_due(client, monkeypatch):
    secret = "whsec_inv"
    from app.core.config import settings as cfg

    monkeypatch.setattr(cfg, "stripe_webhook_secret", secret)

    user = await create_user("whinv@example.com")
    async with async_session_factory() as db:
        db.add(
            Subscription(
                user_id=user.id,
                provider="stripe",
                provider_customer_id="cus_inv",
                provider_subscription_id="sub_inv",
                plan="starter",
                status="active",
            )
        )
        await db.commit()

    event = _fake_event("invoice.payment_failed", event_id="evt_inv", sub_id="sub_inv", customer="cus_inv")
    obj = event["data"]["object"]
    obj["object"] = "invoice"
    obj["id"] = "in_123"
    obj["subscription"] = "sub_inv"
    payload = __import__("json").dumps(event).encode()
    headers = {
        "stripe-signature": _signed_request(secret, payload, int(datetime.now(UTC).timestamp())),
        "content-type": "application/json",
    }
    res = await client.post("/api/webhooks/stripe", content=payload, headers=headers)
    assert res.status_code == 200

    async with async_session_factory() as db:
        sub = (await db.execute(select(Subscription).where(Subscription.provider_subscription_id == "sub_inv"))).scalar_one()
        assert sub.status == "past_due"


@pytest.mark.asyncio
async def test_payload_hash_is_deterministic():
    assert payload_hash(b"abc") == payload_hash(b"abc")
    assert payload_hash(b"abc") != payload_hash(b"abd")
