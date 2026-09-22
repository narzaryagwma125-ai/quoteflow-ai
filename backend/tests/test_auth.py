"""Signup / login / logout / password reset / email verification tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.security.password import hash_password, verify_password
from app.security.tokens import generate_token, hash_token
from tests.conftest import create_user, login, signup


# --- Password hashing ---
@pytest.mark.asyncio
async def test_password_hash_argon2id_roundtrip():
    h = hash_password("super-secret-123")
    assert h.startswith("$argon2id$")
    assert verify_password("super-secret-123", h) is True
    assert verify_password("wrong-password", h) is False
    assert h != "super-secret-123"


# --- Signup ---
@pytest.mark.asyncio
async def test_signup_creates_account_and_sets_cookie(client):
    res = await signup(client, "New.User@Example.com")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["user"]["email"] == "new.user@example.com"  # normalized lowercase
    cookie = client.cookies.get("quoteflow_session")
    assert cookie and len(cookie) > 30


@pytest.mark.asyncio
async def test_signup_duplicate_email_generic_error(client):
    await create_user("dup@example.com")
    res = await signup(client, "dup@example.com")
    assert res.status_code == 400
    assert "could not create account" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signup_weak_password_rejected(client):
    res = await signup(client, "weak@example.com", password="short")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_email_rejected(client):
    res = await signup(client, "not-an-email")
    assert res.status_code == 422


# --- Login / logout ---
@pytest.mark.asyncio
async def test_login_success_sets_http_only_session(client):
    await create_user("login@example.com")
    res = await login(client, "login@example.com")
    set_cookie = res.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert res.json()["user"]["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_login_normalizes_email(client):
    await create_user("normalize@example.com")
    res = await client.post(
        "/api/auth/login",
        json={"email": "  NORMALIZE@EXAMPLE.COM ", "password": "strong-password-123"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["user"]["email"] == "normalize@example.com"


@pytest.mark.asyncio
async def test_login_bad_password_generic_error(client):
    await create_user("gen@example.com")
    res = await client.post(
        "/api/auth/login", json={"email": "gen@example.com", "password": "wrong-password"}
    )
    assert res.status_code == 401
    # No accounts enumeration via differing messages
    assert "invalid email or password" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_unknown_user_same_generic_message(client):
    res = await client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "wrong-password"}
    )
    assert res.status_code == 401
    assert "invalid email or password" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_logout_invalidates_session(client):
    await create_user("logout@example.com")
    await login(client, "logout@example.com")
    await client.post("/api/auth/logout")
    res = await client.get("/api/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_sessions_are_database_backed_and_hashed(client):
    await create_user("sess@example.com")
    await login(client, "sess@example.com")
    from app.db.session import async_session_factory
    from app.models.session import UserSession

    async with async_session_factory() as db:
        from sqlalchemy import select

        rows = (await db.execute(select(UserSession))).scalars().all()
        assert len(rows) == 1
        raw_session = client.cookies.get("quoteflow_session")
        assert rows[0].token_hash == hash_token(raw_session)
        assert rows[0].token_hash != raw_session


# --- Email verification ---
@pytest.mark.asyncio
async def test_email_verification_flow(client):
    await create_user("verify@example.com", is_email_verified=False)
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.token import EmailVerificationToken
    from app.models.user import User

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "verify@example.com"))).scalar_one()
        token = generate_token(32)
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await db.commit()

    res = await client.post("/api/auth/verify-email", json={"token": token})
    assert res.status_code == 200

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "verify@example.com"))).scalar_one()
        assert user.is_email_verified is True

    # token is single-use
    res2 = await client.post("/api/auth/verify-email", json={"token": token})
    assert res2.status_code == 400


# --- Email verification configuration toggle ---
@pytest.mark.asyncio
async def test_signup_verification_disabled_no_token_no_email(client, monkeypatch):
    from sqlalchemy import select

    from app.api import auth as auth_api
    from app.core.config import settings
    from app.db.session import async_session_factory
    from app.models.token import EmailVerificationToken
    from app.models.user import User

    sent = []

    async def _record(to_addr, subject, text, html):
        sent.append(to_addr)

    monkeypatch.setattr(settings, "email_verification_required", False)
    monkeypatch.setattr(auth_api, "send_email", _record)

    res = await signup(client, "No-Verify@Example.com")
    assert res.status_code == 201, res.text
    assert res.json()["user"]["is_email_verified"] is True
    assert sent == []  # verification email neither sent nor logged

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "no-verify@example.com"))).scalar_one()
        assert user.is_email_verified is True
        tokens = (
            await db.execute(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).scalars().all()
        assert tokens == []

    # account is usable immediately
    res_login = await login(client, "no-verify@example.com")
    assert res_login.status_code == 200
    assert res_login.json()["user"]["is_email_verified"] is True


@pytest.mark.asyncio
async def test_signup_verification_enabled_creates_token_and_sends_email(client, monkeypatch):
    from sqlalchemy import select

    from app.api import auth as auth_api
    from app.core.config import settings
    from app.db.session import async_session_factory
    from app.models.token import EmailVerificationToken
    from app.models.user import User

    sent = []

    async def _record(to_addr, subject, text, html):
        sent.append(to_addr)

    monkeypatch.setattr(settings, "email_verification_required", True)
    monkeypatch.setattr(auth_api, "send_email", _record)

    res = await signup(client, "verify-on@example.com")
    assert res.status_code == 201, res.text
    assert res.json()["user"]["is_email_verified"] is False
    assert sent == ["verify-on@example.com"]

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "verify-on@example.com"))).scalar_one()
        tokens = (
            await db.execute(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).scalars().all()
        assert len(tokens) == 1


@pytest.mark.asyncio
async def test_login_unverified_user_succeeds_when_verification_enabled(client, monkeypatch):
    # Current intended behavior: verification gates the verification email, not
    # sign-in. Preserve that no-blocking behavior when verification is enabled.
    from app.core.config import settings

    monkeypatch.setattr(settings, "email_verification_required", True)
    await create_user("unverified@example.com", is_email_verified=False)

    res = await client.post(
        "/api/auth/login", json={"email": "unverified@example.com", "password": "strong-password-123"}
    )
    assert res.status_code == 200


# --- Password reset ---
@pytest.mark.asyncio
async def test_forgot_password_returns_generic_message(client):
    res = await client.post(
        "/api/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert res.status_code == 200
    assert res.json()["message"]


@pytest.mark.asyncio
async def test_password_reset_full_flow(client):
    await create_user("reset@example.com")
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.token import PasswordResetToken
    from app.models.user import User

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "reset@example.com"))).scalar_one()
        token = generate_token(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) + timedelta(minutes=20),
            )
        )
        await db.commit()

    # user's old password works
    await login(client, "reset@example.com")

    res = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "new-strong-password-456"},
    )
    assert res.status_code == 200

    # old sessions invalidated
    res_me = await client.get("/api/me")
    assert res_me.status_code == 401

    # old password no longer works
    res_old = await client.post(
        "/api/auth/login", json={"email": "reset@example.com", "password": "strong-password-123"}
    )
    assert res_old.status_code == 401
    # new password works
    res_new = await login(client, "reset@example.com", password="new-strong-password-456")
    assert res_new.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_token_single_use(client):
    await create_user("resetsingle@example.com")
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.token import PasswordResetToken
    from app.models.user import User

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "resetsingle@example.com"))).scalar_one()
        token = generate_token(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) + timedelta(minutes=20),
            )
        )
        await db.commit()

    first = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "brand-new-password-789"},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "brand-new-password-789"},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_token_expired(client):
    await create_user("resetexp@example.com")
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.token import PasswordResetToken
    from app.models.user import User

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "resetexp@example.com"))).scalar_one()
        token = generate_token(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
        await db.commit()

    res = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "another-new-password-101"},
    )
    assert res.status_code == 400
