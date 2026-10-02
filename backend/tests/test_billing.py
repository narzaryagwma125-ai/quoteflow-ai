from __future__ import annotations
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.subscription import Subscription
from app.services.subscription import get_subscription
from tests.conftest import create_user, login

@pytest.mark.asyncio
async def test_checkout_requires_auth(client):
    res = await client.post("/api/billing/checkout", json={"plan":"starter"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_checkout_rejects_invalid_plan(client):
    await create_user("bill@example.com"); await login(client,"bill@example.com")
    res = await client.post("/api/billing/checkout", json={"plan":"enterprise"})
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_checkout_returns_razorpay_subscription(client, monkeypatch):
    await create_user("bill2@example.com"); await login(client,"bill2@example.com")
    monkeypatch.setattr("app.api.billing.create_subscription", lambda user_id,email,plan: {"id":"sub_rzp_test"})
    from app.core.config import settings
    monkeypatch.setattr(settings,"razorpay_key_id","rzp_test_123")
    res = await client.post("/api/billing/checkout",json={"plan":"starter"})
    assert res.status_code == 200, res.text
    assert res.json()["subscription_id"] == "sub_rzp_test"

@pytest.mark.asyncio
async def test_subscription_summary_free_plan(client):
    await create_user("bill3@example.com",created_at=datetime.now(UTC)-timedelta(days=30))
    await login(client,"bill3@example.com")
    res=await client.get("/api/billing/subscription")
    assert res.status_code==200
    assert res.json()["plan"]=="free"

@pytest.mark.asyncio
async def test_razorpay_webhook_signature_verified_and_subscription_activated(client, monkeypatch):
    import hashlib,hmac,json
    from app.core.config import settings
    secret="webhook_test_secret"; monkeypatch.setattr(settings,"razorpay_webhook_secret",secret)
    user=await create_user("rzpwh@example.com")
    async with async_session_factory() as db:
        db.add(Subscription(user_id=user.id,provider="razorpay",provider_customer_id="",
                            provider_subscription_id="sub_wh",plan="starter",status="incomplete"))
        await db.commit()
    event={"id":"evt_rzp","event":"subscription.activated","payload":{"subscription":{"entity":{
        "id":"sub_wh","plan_id":"plan_starter","customer_id":"cust_1",
        "current_start":int(datetime.now(UTC).timestamp()),
        "current_end":int((datetime.now(UTC)+timedelta(days=30)).timestamp()),
        "notes":{"quoteflow_user_id":str(user.id),"quoteflow_plan":"starter"}}}}}
    raw=json.dumps(event).encode()
    sig=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    res=await client.post("/api/webhooks/razorpay",content=raw,headers={"x-razorpay-signature":sig})
    assert res.status_code==200
    async with async_session_factory() as db:
        sub=(await db.execute(select(Subscription).where(Subscription.provider_subscription_id=="sub_wh"))).scalar_one()
        assert sub.status=="active"

@pytest.mark.asyncio
async def test_duplicate_razorpay_webhook(client, monkeypatch):
    import hashlib,hmac,json
    from app.core.config import settings
    secret="dup_secret"; monkeypatch.setattr(settings,"razorpay_webhook_secret",secret)
    user=await create_user("dup@example.com")
    event={"id":"evt_dup","event":"subscription.activated","payload":{"subscription":{"entity":{
        "id":"sub_dup","customer_id":"cust_dup","notes":{"quoteflow_user_id":str(user.id),"quoteflow_plan":"pro"}}}}}
    raw=json.dumps(event).encode(); sig=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    headers={"x-razorpay-signature":sig}
    first=await client.post("/api/webhooks/razorpay",content=raw,headers=headers)
    second=await client.post("/api/webhooks/razorpay",content=raw,headers=headers)
    assert first.status_code==200 and second.json()["status"]=="duplicate"
