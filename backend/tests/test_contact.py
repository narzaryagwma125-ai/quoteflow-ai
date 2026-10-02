"""Contact form endpoint tests: validation, delivery, spam protection, rate limits."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings

BASE_PAYLOAD = {
    "name": "Jane Customer",
    "email": "jane@example.com",
    "subject": "Billing question",
    "message": "My card was charged twice for the Starter plan. Can you help?",
}


@pytest.mark.asyncio
async def test_contact_valid_message_delivers_to_support(client):
    from app.api import contact

    sent = AsyncMock()
    with patch.object(contact, "send_email", sent):
        res = await client.post("/api/contact", json=BASE_PAYLOAD)

    assert res.status_code == 200
    assert "sent" in res.json()["message"].lower()

    sent.assert_awaited_once()
    to_email, subject, text, html = sent.await_args.args
    assert to_email == settings.support_email
    assert "Billing question" in subject
    assert "Jane Customer" in text
    assert "jane@example.com" in text
    assert "charged twice" in html


@pytest.mark.asyncio
async def test_contact_normalizes_email_and_strips_fields(client):
    from app.api import contact

    sent = AsyncMock()
    with patch.object(contact, "send_email", sent):
        res = await client.post(
            "/api/contact",
            json={
                **BASE_PAYLOAD,
                "email": "Jane@Example.COM",
                "name": "  Jane Customer  ",
            },
        )

    assert res.status_code == 200
    args = sent.await_args.args
    assert "jane@example.com" in args[3]  # normalized lowercase in HTML body
    assert "Jane Customer" in args[2]  # stripped name in text body


@pytest.mark.asyncio
async def test_contact_rejects_missing_fields(client):
    for key in ("name", "email", "subject", "message"):
        payload = dict(BASE_PAYLOAD)
        payload.pop(key)
        res = await client.post("/api/contact", json=payload)
        assert res.status_code == 422, f"expected 422 when {key} is missing"


@pytest.mark.asyncio
async def test_contact_rejects_invalid_email(client):
    res = await client.post("/api/contact", json={**BASE_PAYLOAD, "email": "not-an-email"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_contact_rejects_short_message(client):
    res = await client.post("/api/contact", json={**BASE_PAYLOAD, "message": "short"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_contact_rejects_blank_after_strip(client):
    res = await client.post("/api/contact", json={**BASE_PAYLOAD, "name": "   "})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_contact_rejects_line_breaks_in_name(client):
    res = await client.post(
        "/api/contact", json={**BASE_PAYLOAD, "name": "Jane\nCustomer"}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_contact_honeypot_drops_spam_without_sending(client):
    from app.api import contact

    sent = AsyncMock()
    with patch.object(contact, "send_email", sent):
        res = await client.post(
            "/api/contact", json={**BASE_PAYLOAD, "website": "http://spam.example"}
        )

    assert res.status_code == 200  # bots see success, no signal
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_contact_rate_limit_429(client):
    from app.security import rate_limit

    class _DenyAll:
        async def hit(self, key, limit, window_seconds):
            return False

        async def remaining(self, key, limit, window_seconds):
            return 0

    original = rate_limit.limiter
    rate_limit.limiter = _DenyAll()
    try:
        res = await client.post("/api/contact", json=BASE_PAYLOAD)
        assert res.status_code == 429
    finally:
        rate_limit.limiter = original


@pytest.mark.asyncio
async def test_contact_delivery_failure_returns_503(client):
    from app.api import contact

    with patch.object(contact, "send_email", AsyncMock(side_effect=RuntimeError("smtp down"))):
        res = await client.post("/api/contact", json=BASE_PAYLOAD)

    assert res.status_code == 503
    assert "try again" in res.json()["detail"].lower()