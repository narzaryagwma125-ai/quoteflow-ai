"""Security hardening tests: body limits, origins, headers, log redaction."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.logging import RedactingFilter
from app.db.session import async_session_factory
from app.models.audit_log import AuditLog
from tests.conftest import create_user, login


@pytest.mark.asyncio
async def test_oversized_request_body_rejected(client):
    await create_user("big@example.com")
    await login(client, "big@example.com")
    huge = {"name": "J", "notes": "x" * (1_050_000)}
    res = await client.post("/api/customers", json=huge)
    assert res.status_code in (413, 422)


@pytest.mark.asyncio
async def test_cross_origin_state_change_rejected(client):
    await create_user("origin@example.com")
    await login(client, "origin@example.com")
    res = await client.post(
        "/api/customers",
        json={"name": "Evil"},
        headers={"origin": "https://evil.example.com"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_security_headers_present(client):
    res = await client.get("/api/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") is not None
    assert res.headers.get("content-security-policy") is not None
    assert res.headers.get("permissions-policy") is not None
    assert "ACCESS-CONTROL-ALLOW-ORIGIN" not in {k.upper() for k in res.headers}

    # CORS config never wildcard with credentials
    from app.core.config import settings

    for origin in settings.cors_origins:
        assert origin != "*"


@pytest.mark.asyncio
async def test_session_cookie_flags(client):
    await create_user("cookies@example.com")
    res = await login(client, "cookies@example.com")
    set_cookie = res.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


@pytest.mark.asyncio
async def test_login_response_does_not_expose_secrets(client):
    await create_user("nosecrets@example.com")
    res = await login(client, "nosecrets@example.com")
    assert "password" not in res.text.lower()
    assert "hash" not in res.text.lower()
    assert "token" not in res.text.lower()


@pytest.mark.asyncio
async def test_audit_logs_store_no_passwords_or_bodies(client):
    await create_user("auditlogs@example.com", password="audit-test-pw-123")
    await login(client, "auditlogs@example.com", password="audit-test-pw-123")

    async with async_session_factory() as db:
        rows = (await db.execute(select(AuditLog))).scalars().all()
    for row in rows:
        assert "audit-test-pw-123" not in (row.action + row.ip_hash_or_safe_metadata)
        assert "json" not in row.action


def test_redacting_filter_removes_secrets():
    import logging

    f = RedactingFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="session token=ABC123",
        args=(),
        exc_info=None,
    )
    assert f.filter(record) is True
    assert record.msg == "[REDACTED]"


def test_redacting_filter_allows_safe_records():
    import logging

    f = RedactingFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="quote.created id=5",
        args=(),
        exc_info=None,
    )
    assert f.filter(record) is True
    assert record.msg == "quote.created id=5"


@pytest.mark.asyncio
async def test_frontend_cannot_activate_subscription(client):
    """Subscription status is derived server-side only; there is no client mutation endpoint."""
    await create_user("fsub@example.com")
    await login(client, "fsub@example.com")
    res = await client.post("/api/billing/subscription", json={})
    assert res.status_code in (404, 405)


@pytest.mark.asyncio
async def test_invalid_token_shapes_are_rejected(client):
    res = await client.post(
        "/api/auth/reset-password", json={"token": "short", "password": "long-enough-pw-123"}
    )
    assert res.status_code == 422
    res = await client.post("/api/auth/reset-password", json={"token": "x" * 300, "password": "long-enough-pw-123"})
    assert res.status_code == 422
