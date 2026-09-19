"""Free-trial tests.

Trial is derived from the user's actual signup timestamp (created_at). During
the active trial the user gets Starter plan limits (50 quotes, 50 AI assists,
unlimited customers). Afterwards the normal free-plan monthly limit applies
again, and existing quotes/customers remain accessible.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.subscription import Subscription
from app.services.subscription import PLANS, trial_expires_at, trial_status
from tests.conftest import create_user, login, make_business_profile, quote_payload

FREE_QUOTE_LIMIT = PLANS["free"].quote_monthly_limit
STARTER_QUOTE_LIMIT = PLANS["starter"].quote_monthly_limit
STARTER_AI_LIMIT = PLANS["starter"].ai_monthly_limit


async def _login_new_user(client, email, **user_kwargs):
    user = await create_user(email, **user_kwargs)
    await login(client, email)
    return user


async def _add_profile(user_id: int) -> None:
    async with async_session_factory() as db:
        db.add(make_business_profile(user_id, tax_rate_bps=0))
        await db.commit()


async def _create_quotes(client, count: int, prefix: str) -> None:
    for i in range(count):
        res = await client.post(
            "/api/quotes", json=quote_payload(quote_number=f"{prefix}{i:03d}")
        )
        assert res.status_code == 201, f"failed on quote {i}: {res.text}"


async def _set_subscription(user_id: int, plan: str, status: str = "active") -> None:
    async with async_session_factory() as db:
        db.add(
            Subscription(
                user_id=user_id,
                provider="stripe",
                provider_customer_id=f"cus_{plan}_{user_id}",
                provider_subscription_id=f"sub_{plan}_{user_id}",
                plan=plan,
                status=status,
            )
        )
        await db.commit()


# --- Active trial ---


@pytest.mark.asyncio
async def test_new_user_with_active_trial(client):
    await _login_new_user(client, "trial-new@example.com")

    me = (await client.get("/api/me")).json()
    assert me["trial_active"] is True
    assert me["trial_expired"] is False
    assert me["trial_days_remaining"] == settings.free_trial_days
    assert me["trial_unlimited"] is False

    billing = (await client.get("/api/billing/subscription")).json()
    assert billing["trial_active"] is True
    assert billing["trial_expired"] is False
    assert billing["trial_days_remaining"] == settings.free_trial_days
    assert billing["trial_unlimited"] is False


@pytest.mark.asyncio
async def test_active_trial_uses_starter_limits(client):
    await _login_new_user(client, "trial-limits@example.com")
    billing = (await client.get("/api/billing/subscription")).json()
    assert billing["plan"] == "free"
    assert billing["quotes_limit"] == STARTER_QUOTE_LIMIT
    assert billing["ai_limit"] == STARTER_AI_LIMIT


@pytest.mark.asyncio
async def test_trial_with_one_day_remaining(client):
    await _login_new_user(
        client,
        "trial-1day@example.com",
        created_at=datetime.now(UTC) - timedelta(days=settings.free_trial_days - 1),
    )
    me = (await client.get("/api/me")).json()
    assert me["trial_active"] is True
    assert me["trial_days_remaining"] == 1


@pytest.mark.asyncio
async def test_expired_trial(client):
    await _login_new_user(
        client,
        "trial-expired@example.com",
        created_at=datetime.now(UTC) - timedelta(days=settings.free_trial_days + 1),
    )
    me = (await client.get("/api/me")).json()
    assert me["trial_active"] is False
    assert me["trial_expired"] is True
    assert me["trial_days_remaining"] == 0


# --- Trial quote limit (matches Starter) ---


@pytest.mark.asyncio
async def test_trial_has_50_quote_limit(client):
    user = await _login_new_user(client, "trial-quotelimit@example.com")
    await _add_profile(user.id)
    # The active trial grants Starter levels (50 quotes), not the free plan's 3.
    await _create_quotes(client, STARTER_QUOTE_LIMIT, "Q-TRIAL-")
    res = await client.post(
        "/api/quotes", json=quote_payload(quote_number="Q-TRIAL-999")
    )
    assert res.status_code == 402
    assert "limit" in res.json()["detail"].lower()


# --- Trial AI limit (matches Starter) ---


@pytest.mark.asyncio
async def test_trial_has_50_ai_limit(client):
    user = await _login_new_user(client, "trial-ailimit@example.com")
    from app.services.usage import increment_usage

    async with async_session_factory() as db:
        for _ in range(STARTER_AI_LIMIT):
            await increment_usage(db, user.id, "ai")
        await db.commit()

    # The plan check runs before the AI provider call, so hitting the limit
    # must surface a 402 (not a 503-provider-unavailable).
    res = await client.post(
        "/api/ai/service-description",
        json={"service_name": "Clean", "notes": "kitchen"},
    )
    assert res.status_code == 402


@pytest.mark.asyncio
async def test_trial_ai_still_requires_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "free_trial_enabled", True)
    await _login_new_user(client, "trial-ai@example.com")
    me = (await client.get("/api/me")).json()
    assert me["trial_active"] is True

    res = await client.post(
        "/api/ai/service-description",
        json={"service_name": "Clean", "notes": "kitchen"},
    )
    # No Gemini key in the test env: AI is unavailable (503) rather than free.
    assert res.status_code == 503


# --- Normal monthly limits after trial ---


@pytest.mark.asyncio
async def test_normal_monthly_limit_after_trial(client):
    user = await _login_new_user(
        client,
        "trial-after@example.com",
        created_at=datetime.now(UTC) - timedelta(days=settings.free_trial_days + 1),
    )
    await _add_profile(user.id)

    await _create_quotes(client, FREE_QUOTE_LIMIT, "Q-AFT-")
    res = await client.post(
        "/api/quotes", json=quote_payload(quote_number="Q-AFT-999")
    )
    assert res.status_code == 402
    assert "limit" in res.json()["detail"].lower()


# --- Starter / Business plan limits ---


@pytest.mark.asyncio
async def test_starter_plan_has_50_quote_limit(client):
    user = await _login_new_user(
        client,
        "starter-limit@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await _add_profile(user.id)
    await _set_subscription(user.id, "starter")

    billing = (await client.get("/api/billing/subscription")).json()
    assert billing["plan"] == "starter"
    assert billing["quotes_limit"] == STARTER_QUOTE_LIMIT

    await _create_quotes(client, STARTER_QUOTE_LIMIT, "Q-STARTER-")
    res = await client.post(
        "/api/quotes", json=quote_payload(quote_number="Q-STARTER-999")
    )
    assert res.status_code == 402
    assert "limit" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_business_plan_has_unlimited_quotes(client):
    user = await _login_new_user(
        client,
        "business-unlimited@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await _add_profile(user.id)
    await _set_subscription(user.id, "business")

    billing = (await client.get("/api/billing/subscription")).json()
    assert billing["plan"] == "business"
    assert billing["quotes_limit"] is None
    assert billing["quotes_remaining"] is None
    assert billing["ai_limit"] == PLANS["business"].ai_monthly_limit

    # No quote cap: creating well beyond the Starter limit must succeed.
    await _create_quotes(client, STARTER_QUOTE_LIMIT + 5, "Q-BIZ-")


# --- Expired trial: block new creation, keep existing data ---


@pytest.mark.asyncio
async def test_expired_trial_blocks_new_quote_creation(client):
    user = await _login_new_user(
        client,
        "trial-blocked@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await _add_profile(user.id)

    # The free-plan limit (3) applies after the trial expires.
    await _create_quotes(client, FREE_QUOTE_LIMIT, "Q-BLOCK-")
    res = await client.post(
        "/api/quotes", json=quote_payload(quote_number="Q-BLOCK-999")
    )
    assert res.status_code == 402


@pytest.mark.asyncio
async def test_existing_quotes_remain_accessible_after_trial(client):
    user = await _login_new_user(
        client,
        "trial-keep@example.com",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    await _add_profile(user.id)
    await _create_quotes(client, FREE_QUOTE_LIMIT, "Q-EXIST-")

    lst = await client.get("/api/quotes")
    assert lst.status_code == 200
    body = lst.json()
    assert body["total"] == FREE_QUOTE_LIMIT
    assert all(item["quote_number"].startswith("Q-EXIST-") for item in body["items"])

    detail = await client.get(f"/api/quotes/{body['items'][0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["quote_number"].startswith("Q-EXIST-")


# --- Disabled trial configuration ---


@pytest.mark.asyncio
async def test_disabled_trial_configuration(client, monkeypatch):
    monkeypatch.setattr(settings, "free_trial_enabled", False)
    user = await _login_new_user(client, "trial-disabled@example.com")
    await _add_profile(user.id)

    me = (await client.get("/api/me")).json()
    assert me["trial_active"] is False
    assert me["trial_expired"] is False
    assert me["trial_unlimited"] is False

    # Even a brand-new user must instantly respect the plan limit.
    await _create_quotes(client, FREE_QUOTE_LIMIT, "Q-DIS-")
    res = await client.post(
        "/api/quotes", json=quote_payload(quote_number="Q-DIS-999")
    )
    assert res.status_code == 402


# --- Missing / invalid trial dates ---


def test_missing_created_at_disables_trial():
    class _NoDate:
        created_at = None

    assert trial_expires_at(_NoDate()) is None
    status = trial_status(_NoDate())
    assert status["trial_active"] is False
    assert status["trial_expired"] is False
    assert status["trial_expires_at"] is None


def test_invalid_created_at_disables_trial():
    class _BadDate:
        created_at = "not-a-date"

    assert trial_expires_at(_BadDate()) is None
    status = trial_status(_BadDate())
    assert status["trial_active"] is False
    assert status["trial_expired"] is False


def test_naive_created_at_handled_as_utc(monkeypatch):
    class _Naive:
        created_at = datetime(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr(settings, "free_trial_enabled", True)
    monkeypatch.setattr(settings, "free_trial_days", 5)
    expiry = trial_expires_at(_Naive())
    assert expiry is not None
    assert expiry.tzinfo is not None
    assert expiry.replace(tzinfo=None) == datetime(2026, 1, 6, 12, 0, 0)


@pytest.mark.asyncio
async def test_missing_created_at_enforces_normal_limit():
    from fastapi import HTTPException

    from app.services.subscription import require_plan_feature
    from app.services.usage import increment_usage

    user = await create_user("trial-nodate@example.com")
    # created_at is NOT NULL in the schema, so a missing signup date can only
    # be represented in memory; the enforcement path must still fall back to
    # the normal plan limit instead of granting an unlimited trial.
    user.created_at = None

    async with async_session_factory() as db:
        for _ in range(FREE_QUOTE_LIMIT):
            await increment_usage(db, user.id, "quotes")
        await db.commit()

    async with async_session_factory() as db:
        with pytest.raises(HTTPException) as exc_info:
            await require_plan_feature(db, user, "quotes")
        assert exc_info.value.status_code == 402
