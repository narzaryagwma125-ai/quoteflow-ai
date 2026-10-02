"""Public quote link, accept/reject, CSRF, expiry, and registry tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.quote import Quote
from app.security.tokens import generate_public_quote_token, hash_token
from tests.conftest import (
    create_user,
    login,
    make_business_profile,
    make_customer,
    quote_payload,
)


async def _quoted(client, user_email="pubuser@example.com"):
    user = await create_user(user_email)
    await login(client, user_email)
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=750))
        customer = make_customer(user.id)
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        customer_id = customer.id
    created = await client.post(
        "/api/quotes",
        json=quote_payload(
            quote_number="Q-PUB1",
            customer_id=customer_id,
            items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "100.00", "sort_order": 0}],
        ),
    )
    quote_id = created.json()["quote"]["id"]
    link = (await client.post(f"/api/quotes/{quote_id}/send")).json()["public_link"]
    return client, quote_id, link.rsplit("/", 1)[1]


@pytest.mark.asyncio
async def test_public_quote_accessible_without_login(client):
    _, _, token = await _quoted(client)
    # fresh unauthenticated client
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await anon.get(f"/api/public/quotes/{token}")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["quote_number"] == "Q-PUB1"
        assert body["subtotal_minor"] == 10000
        assert body["tax_minor"] == 750
        assert body["items"][0]["description"] == "Clean"


@pytest.mark.asyncio
async def test_public_quote_does_not_leak_private_data(client):
    _, _, token = await _quoted(client)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await anon.get(f"/api/public/quotes/{token}")
        body = res.json()
        # public payload has no audit/user ids, no customer notes
        assert "user_id" not in body
        assert "public_token_hash" not in body
        assert "responded_by_name" not in body


@pytest.mark.asyncio
async def test_viewing_public_quote_marks_status_viewed(client):
    _, quote_id, token = await _quoted(client)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        await anon.get(f"/api/public/quotes/{token}")
    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        assert quote.status == "viewed"


@pytest.mark.asyncio
async def test_public_token_cannot_be_guessed(client):
    # random tokens are stored hashed; querying by raw token returns 404
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await anon.get("/api/public/quotes/guess-me")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_expired_public_token_rejected(client):
    _, quote_id, token = await _quoted(client)
    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        quote.public_token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await anon.get(f"/api/public/quotes/{token}")
        assert res.status_code == 404

    # status rolled to expired
    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        assert quote.status == "expired"


@pytest.mark.asyncio
async def test_revoked_token_rejected(client):
    _, quote_id, token = await _quoted(client)
    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        quote.public_token_hash = None
        await db.commit()

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await anon.get(f"/api/public/quotes/{token}")
        assert res.status_code == 404


async def _accept_with_csrf(anon, token, accept=True, name="Jane", email="jane@example.com"):
    # load page first to get CSRF cookie
    await anon.get(f"/api/public/quotes/{token}")
    csrf = anon.cookies.get("quoteflow_csrf")
    assert csrf
    path = f"/api/public/quotes/{token}/{'accept' if accept else 'reject'}"
    return await anon.post(path, json={"name": name, "email": email}, headers={"X-CSRF-Token": csrf})


@pytest.mark.asyncio
async def test_accept_quote_with_confirmation_and_csrf(client):
    _, quote_id, token = await _quoted(client)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await _accept_with_csrf(anon, token)
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "accepted"

    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        assert quote.status == "accepted"
        assert quote.responded_by_name == "Jane"
        assert quote.responded_by_email == "jane@example.com"
        assert quote.responded_at is not None


@pytest.mark.asyncio
async def test_accept_without_csrf_token_rejected(client):
    _, _, token = await _quoted(client)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await anon.post(
            f"/api/public/quotes/{token}/accept", json={"name": "Jane", "email": "jane@example.com"}
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_reject_quote(client):
    _, quote_id, token = await _quoted(client)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await _accept_with_csrf(anon, token, accept=False)
        assert res.status_code == 200, res.text

    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        assert quote.status == "rejected"


@pytest.mark.asyncio
async def test_conflicting_repeated_status_change_blocked(client):
    _, quote_id, token = await _quoted(client)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        first = await _accept_with_csrf(anon, token, accept=True)
        assert first.status_code == 200
        csrf = anon.cookies.get("quoteflow_csrf")
        second = await anon.post(
            f"/api/public/quotes/{token}/reject",
            json={"name": "Jane", "email": "jane@example.com"},
            headers={"X-CSRF-Token": csrf},
        )
        assert second.status_code == 400

    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        assert quote.status == "accepted"


@pytest.mark.asyncio
async def test_draft_quote_cannot_be_responded_to(client):
    user = await create_user("pubdraft@example.com")
    await login(client, "pubdraft@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=0))
        await db.commit()
    created = await client.post("/api/quotes", json=quote_payload(quote_number="Q-PUB-DRAFT"))
    quote_id = created.json()["quote"]["id"]

    raw = generate_public_quote_token()
    async with async_session_factory() as db:
        quote = (await db.execute(select(Quote).where(Quote.id == quote_id))).scalar_one()
        quote.public_token_hash = hash_token(raw)
        quote.public_token_expires_at = datetime.now(UTC) + timedelta(days=30)
        await db.commit()

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        res = await _accept_with_csrf(anon, raw)
        assert res.status_code == 400


def _pdf_all_bytes(pdf: bytes) -> bytes:
    """Raw PDF plus decompressed FlateDecode streams for text assertions."""
    import zlib

    chunks = [pdf]
    for part in pdf.split(b"stream")[1:]:
        data = part.split(b"endstream")[0].lstrip(b"\r\n")
        d = zlib.decompressobj()
        try:
            chunks.append(d.decompress(data) + d.flush())
        except zlib.error:
            pass
    return b"".join(chunks)


async def _anonymous():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_accepted_quote_pdf_download_after_acceptance(client):
    """After the customer accepts, the accepted-quote PDF downloads without a
    login, uses the token for authorization, and carries the accepted-quote
    data with the exact filename <number>-Accepted.pdf."""
    _, _quote_id, token = await _quoted(client)

    async with await _anonymous() as anon:
        res = await _accept_with_csrf(anon, token)
        assert res.status_code == 200, res.text

        pdf = await anon.get(f"/api/public/quotes/{token}/pdf")
        assert pdf.status_code == 200, pdf.text
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")
        assert pdf.headers["content-disposition"].startswith(
            'attachment; filename="Q-PUB1-Accepted.pdf"'
        )

        text = _pdf_all_bytes(pdf.content).decode("latin-1")
        assert "Sparkle Cleaning" in text        # business name
        assert "Q-PUB1" in text                  # quote number
        assert "Clean" in text                   # line item
        assert "ACCEPTED" in text                # status badge
        assert "Accepted on" in text             # acceptance date label
        assert datetime.now(UTC).date().isoformat() in text  # acceptance date
        assert "$100.00" in text                 # unit price + subtotal
        assert "$7.50" in text                   # 7.5% tax
        assert "$107.50" in text                 # grand total
        assert "Unit Price" in text


@pytest.mark.asyncio
async def test_accepted_quote_pdf_blocked_before_acceptance(client):
    """The accepted-quote PDF is not served before the customer accepts."""
    _, _quote_id, token = await _quoted(client)
    async with await _anonymous() as anon:
        res = await anon.get(f"/api/public/quotes/{token}/pdf")
        assert res.status_code == 400
        assert "accepted" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_accepted_quote_pdf_blocked_after_rejection(client):
    """A rejected quote never yields the accepted-quote PDF."""
    _, _quote_id, token = await _quoted(client)
    async with await _anonymous() as anon:
        res = await _accept_with_csrf(anon, token, accept=False)
        assert res.status_code == 200, res.text
        pdf = await anon.get(f"/api/public/quotes/{token}/pdf")
        assert pdf.status_code == 400


@pytest.mark.asyncio
async def test_accepted_quote_pdf_invalid_token_rejected(client):
    """An invalid/guessed token is rejected; the quote ID alone is never used."""
    async with await _anonymous() as anon:
        res = await anon.get("/api/public/quotes/guess-me/pdf")
        assert res.status_code == 404
