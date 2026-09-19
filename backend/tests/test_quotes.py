"""Quote CRUD, calculation integrity, limits, and token security tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.quote import Quote, QuoteItem
from app.security.tokens import hash_token
from tests.conftest import (
    create_user,
    login,
    make_business_profile,
    make_customer,
    quote_payload,
)


async def _authed(user_email="q@example.com"):
    user = await create_user(user_email)
    return user


@pytest.mark.asyncio
async def test_quote_requires_auth(client):
    res = await client.get("/api/quotes")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_quote_calculates_totals_on_backend(client):
    user = await _authed()
    await login(client, "q@example.com")

    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=750))
        customer = make_customer(user.id)
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        customer_id = customer.id

    payload = quote_payload(
        quote_number="Q-2026-0001",
        customer_id=customer_id,
        items=[
            {"description": "Deep clean", "quantity": "2", "unit": "hr", "unit_price": "100.00", "sort_order": 0},
            {"description": "Windows", "quantity": "1", "unit": "job", "unit_price": "50.00", "sort_order": 1},
        ],
    )
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()["quote"]
    assert body["subtotal_minor"] == 25000
    assert body["discount_minor"] == 0
    assert body["tax_minor"] == 1875  # 7.5% of 250.00
    assert body["total_minor"] == 26875
    assert body["breakdown"]["tax_rate_percent"] == "7.5"


@pytest.mark.asyncio
async def test_frontend_submitted_totals_are_ignored(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    # try to smuggle a fake total
    payload = quote_payload(
        quote_number="Q-2026-0002",
        items=[
            {"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "100.00", "sort_order": 0},
        ],
    )
    payload["total_minor"] = 1
    payload["subtotal_minor"] = 999999
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 201
    body = res.json()["quote"]
    assert body["subtotal_minor"] == 10000
    assert body["total_minor"] == 10000


@pytest.mark.asyncio
async def test_create_quote_defaults_to_inr_currency(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    payload = quote_payload(
        quote_number="Q-2026-INR",
        items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "100.00", "sort_order": 0}],
    )
    payload.pop("currency")
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 201, res.text
    assert res.json()["quote"]["currency"] == "INR"


@pytest.mark.asyncio
async def test_create_quote_accepts_all_supported_currencies(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    for i, currency in enumerate(("USD", "CAD", "INR", "GBP", "AUD")):
        res = await client.post(
            "/api/quotes",
            json=quote_payload(
                quote_number=f"Q-CURR-{i}",
                currency=currency,
            ),
        )
        assert res.status_code == 201, f"{currency}: {res.text}"
        assert res.json()["quote"]["currency"] == currency


@pytest.mark.asyncio
async def test_create_quote_rejects_unsupported_currency(client):
    await _authed()
    await login(client, "q@example.com")
    res = await client.post(
        "/api/quotes",
        json=quote_payload(quote_number="Q-CURR-BAD", currency="EUR"),
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_discount_applied_and_validated(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    payload = quote_payload(
        quote_number="Q-2026-0003",
        discount="20.00",
        items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "100.00", "sort_order": 0}],
    )
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 201
    body = res.json()["quote"]
    assert body["discount_minor"] == 2000
    assert body["total_minor"] == 8000

    # discount > subtotal rejected
    payload["discount"] = "200.00"
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_negative_quantity_and_price_rejected(client):
    await _authed()
    await login(client, "q@example.com")

    payload = quote_payload(
        quote_number="Q-X1",
        items=[{"description": "X", "quantity": "-1", "unit": "", "unit_price": "10.00", "sort_order": 0}],
    )
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 422

    payload = quote_payload(
        quote_number="Q-X2",
        items=[{"description": "X", "quantity": "1", "unit": "", "unit_price": "-10.00", "sort_order": 0}],
    )
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_quote_number_unique_per_business(client):
    await _authed()
    await login(client, "q@example.com")
    payload = quote_payload(quote_number="Q-2026-100")
    assert (await client.post("/api/quotes", json=payload)).status_code == 201
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_update_quote_recalculates(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    created = await client.post(
        "/api/quotes",
        json=quote_payload(
            quote_number="Q-U1",
            items=[{"description": "A", "quantity": "1", "unit": "", "unit_price": "10.00", "sort_order": 0}],
        ),
    )
    quote_id = created.json()["quote"]["id"]

    res = await client.put(
        f"/api/quotes/{quote_id}",
        json={
            "items": [
                {"description": "A", "quantity": "3", "unit": "", "unit_price": "10.00", "sort_order": 0},
                {"description": "B", "quantity": "1", "unit": "", "unit_price": "5.50", "sort_order": 1},
            ]
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["subtotal_minor"] == 3550
    assert body["total_minor"] == 3550
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_free_plan_quote_limit(client):
    # Backdate the account so the 5-day free trial has already expired.
    user = await create_user(
        "q@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    for i in range(3):
        res = await client.post(
            "/api/quotes", json=quote_payload(quote_number=f"Q-2026-{i:04d}")
        )
        assert res.status_code == 201, res.text

    res = await client.post("/api/quotes", json=quote_payload(quote_number="Q-2026-9999"))
    assert res.status_code == 402
    assert "limit" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_quote_stats(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    await client.post("/api/quotes", json=quote_payload(quote_number="Q-S1"))

    stats = await client.get("/api/quotes/stats")
    assert stats.status_code == 200
    data = stats.json()
    assert data["total"] == 1
    assert data["draft"] == 1


@pytest.mark.asyncio
async def test_send_quote_creates_secure_public_token(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    created = await client.post("/api/quotes", json=quote_payload(quote_number="Q-T1"))
    quote_id = created.json()["quote"]["id"]

    res = await client.post(f"/api/quotes/{quote_id}/send")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["quote"]["status"] == "sent"
    public_link = body["public_link"]
    assert public_link and "/q/" in public_link
    token = public_link.rsplit("/", 1)[1]

    # DB stores only the hash
    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        assert quote.public_token_hash == hash_token(token)
        assert quote.public_token_hash != token


@pytest.mark.asyncio
async def test_revoke_link_invalidates_token(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    created = await client.post("/api/quotes", json=quote_payload(quote_number="Q-R1"))
    quote_id = created.json()["quote"]["id"]
    link = (await client.post(f"/api/quotes/{quote_id}/send")).json()["public_link"]
    token = link.rsplit("/", 1)[1]

    res = await client.post(f"/api/quotes/{quote_id}/revoke-link")
    assert res.status_code == 200
    pub = await client.get(f"/api/public/quotes/{token}")
    assert pub.status_code == 404


@pytest.mark.asyncio
async def test_public_tokens_are_high_entropy(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    created = await client.post("/api/quotes", json=quote_payload(quote_number="Q-H1"))
    quote_id = created.json()["quote"]["id"]
    link = (await client.post(f"/api/quotes/{quote_id}/send")).json()["public_link"]
    token = link.rsplit("/", 1)[1]
    assert len(token) >= 40  # 32 bytes url-safe ~ 43 chars


@pytest.mark.asyncio
async def test_decimal_quantity_and_rounding(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    payload = quote_payload(
        quote_number="Q-D1",
        items=[{"description": "Hours", "quantity": "2.5", "unit": "hr", "unit_price": "40.00", "sort_order": 0}],
    )
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 201, res.text
    assert res.json()["quote"]["subtotal_minor"] == 10000


@pytest.mark.asyncio
async def test_quote_list_returns_paginated_shape(client):
    user = await _authed()
    await login(client, "q@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    await client.post("/api/quotes", json=quote_payload(quote_number="Q-L1"))

    res = await client.get("/api/quotes")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body and "total" in body
    assert body["total"] == 1
    assert body["items"][0]["quote_number"] == "Q-L1"


# --- Dev-only quote-limit bypass tests ---


@pytest.mark.asyncio
async def test_dev_quote_limit_bypass(client):
    """With DEV_IGNORE_QUOTE_LIMITS=true and APP_ENV=development, the 3/month
    free-plan limit is ignored even after the 5-day trial has expired."""
    from app.core.config import settings

    user = await create_user(
        "dev@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await login(client, "dev@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    prev_env = settings.app_env
    prev_flag = settings.dev_ignore_quote_limits
    settings.app_env = "development"
    settings.dev_ignore_quote_limits = True
    try:
        for i in range(5):
            res = await client.post(
                "/api/quotes",
                json=quote_payload(quote_number=f"Q-DEV-{i:04d}"),
            )
            assert res.status_code == 201, res.text
    finally:
        settings.app_env = prev_env
        settings.dev_ignore_quote_limits = prev_flag


@pytest.mark.asyncio
async def test_dev_quote_limit_honored_when_flag_off(client):
    """When DEV_IGNORE_QUOTE_LIMITS=false, the normal free-plan limit applies."""
    from app.core.config import settings

    user = await create_user(
        "devflag@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await login(client, "devflag@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    prev_env = settings.app_env
    prev_flag = settings.dev_ignore_quote_limits
    settings.app_env = "development"
    settings.dev_ignore_quote_limits = False
    try:
        for i in range(3):
            res = await client.post(
                "/api/quotes",
                json=quote_payload(quote_number=f"Q-NOFLAG-{i:04d}")
            )
            assert res.status_code == 201, res.text

        res = await client.post(
            "/api/quotes",
            json=quote_payload(quote_number="Q-NOFLAG-9999"),
        )
        assert res.status_code == 402
    finally:
        settings.app_env = prev_env
        settings.dev_ignore_quote_limits = prev_flag


@pytest.mark.asyncio
async def test_dev_quote_limit_never_applies_in_production(client):
    """DEV_IGNORE_QUOTE_LIMITS=true must have no effect when APP_ENV=production."""
    from app.core.config import settings

    user = await create_user(
        "prod@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await login(client, "prod@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()

    prev_env = settings.app_env
    prev_flag = settings.dev_ignore_quote_limits
    settings.app_env = "production"
    settings.dev_ignore_quote_limits = True
    try:
        for i in range(3):
            res = await client.post(
                "/api/quotes",
                json=quote_payload(quote_number=f"Q-PROD-{i:04d}")
            )
            assert res.status_code == 201, res.text

        res = await client.post(
            "/api/quotes",
            json=quote_payload(quote_number="Q-PROD-9999"),
        )
        assert res.status_code == 402
    finally:
        settings.app_env = prev_env
        settings.dev_ignore_quote_limits = prev_flag


@pytest.mark.asyncio
async def test_money_convention_round_trip_equal_create_and_detail_api(client):
    """Regression: quantity must never be *100 and dollars must convert to cents
    exactly once. qty 3 * unit price 150.00 => line 450, tax 12% => 54, total 504,
    identical across POST /quotes, PUT /quotes/{id}, and GET /quotes/{id}."""
    user = await create_user("money@example.com")
    await login(client, "money@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=1200))  # 12%
        await db.commit()

    payload = quote_payload(
        quote_number="Q-MONEY-1",
        discount="0",
        items=[
            {"description": "Deep clean", "quantity": "3", "unit": "hour", "unit_price": "150.00", "sort_order": 0},
        ],
    )

    # 1) Quantity 3 remains 3 after saving (never multiplied by 100).
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 201, res.text
    created = res.json()["quote"]
    item = created["items"][0]
    assert item["quantity"] == "3"
    assert item["unit_price_minor"] == 15000          # 2) 150.00 -> cents, exactly once
    assert item["line_total_minor"] == 45000          # 3) 3 * 150.00 = 450.00
    assert created["subtotal_minor"] == 45000
    assert created["tax_minor"] == 5400               # 4) 12% of 450.00 = 54.00
    assert created["total_minor"] == 50400            # 5) 450.00 + 54.00 = 504.00
    assert created["breakdown"]["tax_rate_percent"] == "12"

    quote_id = created["id"]

    # 6) PUT update uses the same money convention (endpoint returns bare QuotePublic).
    res = await client.put(f"/api/quotes/{quote_id}", json=payload)
    assert res.status_code == 200, res.text
    assert res.json()["items"][0]["quantity"] == "3"
    assert res.json()["total_minor"] == 50400

    # 6b) GET detail agrees with the create API.
    detail = await client.get(f"/api/quotes/{quote_id}")
    assert detail.status_code == 200
    d = detail.json()
    assert d["items"][0]["quantity"] == "3"
    assert d["items"][0]["unit_price_minor"] == item["unit_price_minor"]
    assert d["items"][0]["line_total_minor"] == item["line_total_minor"]
    assert d["subtotal_minor"] == created["subtotal_minor"]
    assert d["tax_minor"] == created["tax_minor"]
    assert d["total_minor"] == created["total_minor"]

    # list API renders the same values too
    listing = await client.get("/api/quotes")
    assert listing.status_code == 200
    listed = next(x for x in listing.json()["items"] if x["id"] == quote_id)
    assert listed["total_minor"] == 50400


@pytest.mark.asyncio
async def test_existing_quote_rows_remain_readable(client):
    """Pre-existing rows (major-unit dollars already stored as cents) must round-trip
    unchanged with no destructive migration on the fix."""
    user = await create_user("oldquote@example.com")
    await login(client, "oldquote@example.com")
    async with async_session_factory() as db:
        quote = Quote(
            user_id=user.id,
            customer_id=None,
            quote_number="Q-OLD-1",
            status="sent",
            issue_date=date(2026, 9, 1),
            expiry_date=None,
            currency="USD",
            subtotal_minor=45000,
            discount_minor=0,
            tax_minor=5400,
            total_minor=50400,
            notes="",
            terms="",
        )
        db.add(quote)
        await db.flush()
        db.add(
            QuoteItem(
                quote_id=quote.id,
                description="Deep clean",
                quantity="3",
                unit="hour",
                unit_price_minor=15000,
                line_total_minor=45000,
                sort_order=0,
            )
        )
        await db.commit()
        await db.refresh(quote)
        quote_id = quote.id

    detail = await client.get(f"/api/quotes/{quote_id}")
    assert detail.status_code == 200
    d = detail.json()
    assert d["quote_number"] == "Q-OLD-1"
    assert d["status"] == "sent"
    assert d["items"][0]["quantity"] == "3"
    assert d["items"][0]["unit_price_minor"] == 15000
    assert d["items"][0]["line_total_minor"] == 45000
    assert d["total_minor"] == 50400

    listing = await client.get("/api/quotes")
    assert listing.status_code == 200
    assert any(item["id"] == quote_id for item in listing.json()["items"])
