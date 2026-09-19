from __future__ import annotations

import os
import tempfile

# Configure test environment BEFORE importing the app.
os.environ["APP_ENV"] = "test"
_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_path = _db_file.name
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test_secret_key_32_characters_long!!"
os.environ["FRONTEND_URL"] = "http://testserver"
os.environ["SESSION_COOKIE_SECURE"] = "false"

import pytest_asyncio  # noqa: E402, F401
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402, F401
from app.db.base import Base  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.main import app  # noqa: E402


def _test_engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(os.environ["DATABASE_URL"])


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    """Full schema reset per test for complete isolation."""
    engine = _test_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


class _StubLimiter:
    async def hit(self, key, limit, window_seconds):
        return True

    async def remaining(self, key, limit, window_seconds):
        return limit


@pytest_asyncio.fixture(autouse=True)
async def _disable_rate_limits(request):
    from app.security import rate_limit

    if "real_limits" in request.keywords:
        yield
        return
    stub = _StubLimiter()
    original = rate_limit.limiter
    rate_limit.limiter = stub
    yield
    rate_limit.limiter = original


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session


async def create_user(email: str, password: str = "strong-password-123", **kwargs):
    from sqlalchemy import select

    from app.models.user import User
    from app.security.password import hash_password

    async with async_session_factory() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            return existing
        user = User(
            email=email,
            password_hash=hash_password(password),
            is_email_verified=kwargs.pop("is_email_verified", True),
            **kwargs,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def login(client: AsyncClient, email: str, password: str = "strong-password-123"):
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


async def signup(client: AsyncClient, email: str, password: str = "strong-password-123"):
    return await client.post("/api/auth/signup", json={"email": email, "password": password})


def make_business_profile(user_id: int, **overrides):
    from app.models.business_profile import BusinessProfile

    data = {
        "user_id": user_id,
        "business_name": "Sparkle Cleaning",
        "owner_name": "Alex Owner",
        "email": "owner@example.com",
        "country": "US",
        "currency": "USD",
        "timezone": "America/New_York",
        "tax_rate_bps": 750,  # 7.5%
    }
    data.update(overrides)
    return BusinessProfile(**data)


def make_customer(user_id: int, **overrides):
    from app.models.customer import Customer

    data = {"user_id": user_id, "name": "Jane Customer", "email": "jane@example.com"}
    data.update(overrides)
    return Customer(**data)


def quote_payload(**overrides):
    payload = {
        "quote_number": "Q-2026-0001",
        "issue_date": "2026-09-13",
        "expiry_date": "2026-10-13",
        "currency": "USD",
        "discount": "0",
        "notes": "Thank you for your interest.",
        "terms": "Payment due within 14 days.",
        "items": [
            {
                "description": "Deep house cleaning",
                "quantity": "1",
                "unit": "job",
                "unit_price": "249.99",
                "sort_order": 0,
            }
        ],
    }
    payload.update(overrides)
    return payload
