"""User isolation and authorization tests: A must never access B's data."""

from __future__ import annotations

import pytest

from tests.conftest import create_user, login, make_customer, quote_payload


async def _setup_users(client):
    await create_user("user-a@example.com")
    await create_user("user-b@example.com")


async def _create_data_for_b():
    from datetime import date

    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.quote import Quote
    from app.models.user import User

    async with async_session_factory() as session:
        b_user = (await session.execute(select(User).where(User.email == "user-b@example.com"))).scalar_one()
        b_customer = make_customer(b_user.id, name="Bob's customer")
        session.add(b_customer)
        await session.flush()

        quote = Quote(
            user_id=b_user.id,
            customer_id=b_customer.id,
            quote_number="Q-B",
            status="draft",
            issue_date=date(2026, 9, 1),
            subtotal_minor=1000,
            total_minor=1000,
        )
        session.add(quote)
        await session.commit()
        await session.refresh(quote)
        return b_customer.id, quote.id


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_customer(client):
    await _setup_users(client)
    customer_id, _ = await _create_data_for_b()
    await login(client, "user-a@example.com")
    res = await client.get(f"/api/customers/{customer_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_update_user_b_customer(client):
    await _setup_users(client)
    customer_id, _ = await _create_data_for_b()
    await login(client, "user-a@example.com")
    res = await client.put(f"/api/customers/{customer_id}", json={"name": "hacked"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_quote(client):
    await _setup_users(client)
    _, quote_id = await _create_data_for_b()
    await login(client, "user-a@example.com")
    res = await client.get(f"/api/quotes/{quote_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_delete_user_b_quote(client):
    await _setup_users(client)
    _, quote_id = await _create_data_for_b()
    await login(client, "user-a@example.com")
    res = await client.delete(f"/api/quotes/{quote_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_download_user_b_pdf(client):
    await _setup_users(client)
    _, quote_id = await _create_data_for_b()
    await login(client, "user-a@example.com")
    res = await client.post(f"/api/quotes/{quote_id}/generate-pdf")
    assert res.status_code in (403, 404)
    assert res.headers.get("content-type") != "application/pdf"


@pytest.mark.asyncio
async def test_user_a_cannot_revoke_user_b_link(client):
    await _setup_users(client)
    _, quote_id = await _create_data_for_b()
    await login(client, "user-a@example.com")
    res = await client.post(f"/api/quotes/{quote_id}/revoke-link")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_quote_create_with_other_users_customer_rejected(client):
    await _setup_users(client)
    customer_id, _ = await _create_data_for_b()
    await login(client, "user-a@example.com")
    payload = quote_payload(customer_id=customer_id)
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_user_a_list_does_not_include_user_b_data(client):
    await _setup_users(client)
    _, quote_id = await _create_data_for_b()
    await login(client, "user-a@example.com")
    res = await client.get("/api/quotes")
    assert res.status_code == 200
    ids = [q["id"] for q in res.json()["items"]]
    assert quote_id not in ids
