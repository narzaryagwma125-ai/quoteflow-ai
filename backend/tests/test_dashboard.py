"""Dashboard statistics: per-currency totals, status counts, plan usage,
search/filters, DOCX download, and empty states. Totals are never blended
across currencies and are always derived from the database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.quote import Quote
from tests.conftest import (
    create_user,
    login,
    make_business_profile,
    make_customer,
    quote_payload,
)

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _fresh_user(client, email: str, *, backdate_days: int | None = None):
    kwargs = {}
    if backdate_days:
        kwargs["created_at"] = datetime.now(UTC) - timedelta(days=backdate_days)
    user = await create_user(email, **kwargs)
    await login(client, email)
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    return user


async def _create(client, **overrides) -> dict:
    res = await client.post("/api/quotes", json=quote_payload(**overrides))
    assert res.status_code == 201, res.text
    return res.json()["quote"]


async def _set_status(quote_id: int, status: str) -> None:
    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        quote.status = status
        await db.commit()


async def _stats(client) -> dict:
    res = await client.get("/api/quotes/stats")
    assert res.status_code == 200, res.text
    return res.json()


# ── Empty dashboard ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_empty_dashboard_has_no_fake_zeros(client):
    await _fresh_user(client, "dash0@example.com")
    data = await _stats(client)
    assert data["total"] == 0
    assert data["draft"] == 0
    assert data["sent"] == 0
    assert data["viewed"] == 0
    assert data["accepted"] == 0
    assert data["rejected"] == 0
    assert data["expired"] == 0
    assert data["cancelled"] == 0
    assert data["created_this_month"] == 0
    # No currency buckets at all — never a misleading $0.00 figure.
    assert data["totals_by_currency"] == []


# ── Per-currency totals ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_groups_by_currency_and_excludes_cancelled(client):
    await _fresh_user(client, "dash1@example.com")

    await _create(
        client,
        quote_number="Q-USD-1",
        currency="USD",
        discount="10.00",
        items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "100.00", "sort_order": 0}],
    )
    cad = await _create(
        client,
        quote_number="Q-CAD-1",
        currency="CAD",
        items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "50.00", "sort_order": 0}],
    )
    inr = await _create(
        client,
        quote_number="Q-INR-1",
        currency="INR",
        items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "5000.00", "sort_order": 0}],
    )
    gbp = await _create(
        client,
        quote_number="Q-GBP-1",
        currency="GBP",
        items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "60.00", "sort_order": 0}],
    )
    aud = await _create(
        client,
        quote_number="Q-AUD-1",
        currency="AUD",
        items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "70.00", "sort_order": 0}],
    )
    cancelled = await _create(
        client,
        quote_number="Q-CANCEL-1",
        currency="USD",
        items=[{"description": "Void", "quantity": "1", "unit": "job", "unit_price": "200.00", "sort_order": 0}],
    )
    await _set_status(cad["id"], "sent")
    await _set_status(inr["id"], "viewed")
    await _set_status(gbp["id"], "accepted")
    await _set_status(aud["id"], "sent")
    await _set_status(cancelled["id"], "cancelled")

    data = await _stats(client)
    assert data["total"] == 6
    assert data["draft"] == 1
    assert data["sent"] == 2
    assert data["viewed"] == 1
    assert data["accepted"] == 1
    assert data["cancelled"] == 1

    by_currency = {g["currency"]: g for g in data["totals_by_currency"]}
    assert set(by_currency) == {"USD", "CAD", "INR", "GBP", "AUD"}

    # USD quote: 100.00 - 10.00 discount.
    assert by_currency["USD"] == {
        "currency": "USD",
        "currency_symbol": "$",
        "count": 1,
        "subtotal_minor": 10000,
        "discount_minor": 1000,
        "tax_minor": 0,
        "total_minor": 9000,
    }
    # CAD: excluded cancelled? No — the cancelled quote was USD; CAD is clean.
    assert by_currency["CAD"]["count"] == 1
    assert by_currency["CAD"]["subtotal_minor"] == 5000
    assert by_currency["CAD"]["total_minor"] == 5000
    assert by_currency["CAD"]["currency_symbol"] == "CA$"
    assert by_currency["INR"]["subtotal_minor"] == 500000
    assert by_currency["INR"]["total_minor"] == 500000
    assert by_currency["INR"]["currency_symbol"] == "\u20b9"
    assert by_currency["GBP"]["subtotal_minor"] == 6000
    assert by_currency["GBP"]["total_minor"] == 6000
    assert by_currency["GBP"]["currency_symbol"] == "\u00a3"
    assert by_currency["AUD"]["subtotal_minor"] == 7000
    assert by_currency["AUD"]["total_minor"] == 7000
    assert by_currency["AUD"]["currency_symbol"] == "A$"


@pytest.mark.asyncio
async def test_cancelled_quotes_excluded_from_totals_not_statuses(client):
    await _fresh_user(client, "dash2@example.com")
    q = await _create(client, quote_number="Q-VOID-1")
    await _set_status(q["id"], "cancelled")
    data = await _stats(client)
    assert data["cancelled"] == 1
    assert data["total"] == 1
    assert data["totals_by_currency"] == []


@pytest.mark.asyncio
async def test_stats_status_counts_all_seven(client):
    await _fresh_user(client, "dash3@example.com")
    status_by_quote = {
        "Q-D": "draft",
        "Q-S": "sent",
        "Q-V": "viewed",
        "Q-A": "accepted",
        "Q-R": "rejected",
        "Q-E": "expired",
        "Q-C": "cancelled",
    }
    for number, status in status_by_quote.items():
        q = await _create(client, quote_number=number)
        await _set_status(q["id"], status)

    data = await _stats(client)
    for status in status_by_quote.values():
        assert data[status] == 1
    assert data["total"] == 7


# ── List search & filters ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_search_by_customer_name_and_number(client):
    user = await _fresh_user(client, "dash4@example.com")
    async with async_session_factory() as db:
        customer = make_customer(user.id, name="Acme Roofing Co.")
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        customer_id = customer.id

    await _create(client, quote_number="Q-SRCH-1", customer_id=customer_id)
    await _create(client, quote_number="Q-SRCH-2")

    res = await client.get("/api/quotes?q=acme")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["quote_number"] == "Q-SRCH-1"
    assert body["items"][0]["customer_name"] == "Acme Roofing Co."

    res = await client.get("/api/quotes?q=Q-SRCH-2")
    assert res.json()["total"] == 1

    res = await client.get("/api/quotes?q=doesnotexist")
    assert res.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_filters_by_currency_and_date_range(client):
    await _fresh_user(client, "dash5@example.com")
    await _create(client, quote_number="Q-AUG", currency="CAD", issue_date="2026-08-01")
    await _create(client, quote_number="Q-SEP", currency="USD", issue_date="2026-09-01")
    await _create(client, quote_number="Q-OCT", currency="USD", issue_date="2026-10-01")

    assert (await client.get("/api/quotes?currency=USD")).json()["total"] == 2
    assert (await client.get("/api/quotes?currency=CAD")).json()["total"] == 1
    assert (await client.get("/api/quotes?date_from=2026-09-01")).json()["total"] == 2
    assert (await client.get("/api/quotes?date_to=2026-08-31")).json()["total"] == 1
    assert (await client.get("/api/quotes?currency=CAD&date_from=2026-08-01&date_to=2026-08-31")).json()["total"] == 1


# ── Immediate updates after CRUD ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_then_delete_updates_stats(client):
    await _fresh_user(client, "dash6@example.com")
    assert (await _stats(client))["total"] == 0

    q = await _create(client, quote_number="Q-CRUD-1")
    data = await _stats(client)
    assert data["total"] == 1
    assert data["totals_by_currency"][0]["count"] == 1

    res = await client.delete(f"/api/quotes/{q['id']}")
    assert res.status_code == 200
    data = await _stats(client)
    assert data["total"] == 0
    assert data["totals_by_currency"] == []


# ── Plan usage ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_free_plan_usage_reports_limit_met(client):
    await _fresh_user(client, "dash7@example.com", backdate_days=30)
    for i in range(3):
        await _create(client, quote_number=f"Q-LIMIT-{i}")

    res = await client.get("/api/billing/subscription")
    assert res.status_code == 200
    body = res.json()
    assert body["plan"] == "free"
    assert body["status"] == "free"  # never "none"
    assert body["quotes_used"] == 3
    assert body["quotes_limit"] == 3
    assert body["quotes_remaining"] == 0
    assert body["ai_used"] == 0
    assert body["ai_limit"] == 10


# ── DOCX download ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_download_docx_default_template(client):
    await _fresh_user(client, "dash8@example.com")
    q = await _create(client, quote_number="Q-DOCX-1")
    res = await client.get(f"/api/quotes/{q['id']}/download-docx")
    assert res.status_code == 200
    assert res.headers["content-type"] == _DOCX_MIME
    assert res.content[:4] == b"PK\x03\x04"
    assert 'filename="quotation-Q-DOCX-1.docx"' in res.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_docx_requires_ownership(client):
    await _fresh_user(client, "dash9a@example.com")
    q = await _create(client, quote_number="Q-OWN-1")

    await create_user("dash9b@example.com")
    await login(client, "dash9b@example.com")
    res = await client.get(f"/api/quotes/{q['id']}/download-docx")
    assert res.status_code == 404
