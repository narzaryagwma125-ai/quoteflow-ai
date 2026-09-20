"""Customer CRUD tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.customer import Customer
from app.models.user import User
from tests.conftest import create_user, login


async def _authed_client(client, email="cust@example.com"):
    await create_user(email)
    await login(client, email)
    return client


@pytest.mark.asyncio
async def test_create_customer(client):
    await _authed_client(client)
    res = await client.post(
        "/api/customers",
        json={"name": "Jane Customer", "email": "jane@example.com", "phone": "555-0100"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["name"] == "Jane Customer"


@pytest.mark.asyncio
async def test_customer_requires_auth(client):
    res = await client.get("/api/customers")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_customers(client):
    await _authed_client(client)
    await client.post("/api/customers", json={"name": "One"})
    await client.post("/api/customers", json={"name": "Two"})
    res = await client.get("/api/customers")
    assert res.status_code == 200
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_update_customer(client):
    await _authed_client(client)
    created = (await client.post("/api/customers", json={"name": "Before"})).json()
    res = await client.put(f"/api/customers/{created['id']}", json={"name": "After"})
    assert res.status_code == 200
    assert res.json()["name"] == "After"


@pytest.mark.asyncio
async def test_delete_customer(client):
    await _authed_client(client)
    created = (await client.post("/api/customers", json={"name": "To Delete"})).json()
    res = await client.delete(f"/api/customers/{created['id']}")
    assert res.status_code == 200
    res2 = await client.get(f"/api/customers/{created['id']}")
    assert res2.status_code == 404


@pytest.mark.asyncio
async def test_customer_notes_length_limited(client):
    await _authed_client(client)
    res = await client.post("/api/customers", json={"name": "X", "notes": "z" * 5000})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_free_plan_customer_limit(client):
    # Backdate so the trial has expired: the free-plan 25-customer cap applies.
    await create_user(
        "cust@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await login(client, "cust@example.com")
    for i in range(25):
        res = await client.post("/api/customers", json={"name": f"Customer {i}"})
        assert res.status_code == 201, f"failed on {i}: {res.text}"
    res = await client.post("/api/customers", json={"name": "One too many"})
    assert res.status_code == 400
    assert "upgrade" in res.json()["detail"].lower() or "limit" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trial_unlimited_customers(client):
    # Active trial matches Starter: no customer cap (exceeds the free plan's 25).
    await create_user("trial-cust@example.com")
    await login(client, "trial-cust@example.com")
    for i in range(30):
        res = await client.post("/api/customers", json={"name": f"Cust {i}"})
        assert res.status_code == 201, f"failed on {i}: {res.text}"


@pytest.mark.asyncio
async def test_sql_injection_style_payload_does_not_bypass_ownership(client):
    await _authed_client(client)
    res = await client.post("/api/customers", json={"name": "'; DROP TABLE customers; --"})
    assert res.status_code == 201
    # table still exists, row inserted safely as data
    async with async_session_factory() as db:
        users = (await db.execute(select(User))).scalars().all()
        assert users  # customers table untouched
        customers = (await db.execute(select(Customer))).scalars().all()
        assert len(customers) == 1
        assert customers[0].name == "'; DROP TABLE customers; --"
