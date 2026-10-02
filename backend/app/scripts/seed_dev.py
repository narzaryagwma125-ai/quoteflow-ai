"""Development-only seed script. NEVER run in production.

Creates a demo business owner with a profile and a single test customer —
no production fake data is ever inserted.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.business_profile import BusinessProfile
from app.models.customer import Customer
from app.models.user import User
from app.security.password import hash_password

DEV_USER_EMAIL = os.getenv("SEED_EMAIL", "demo@example.com")
DEV_USER_PASSWORD = os.getenv("SEED_PASSWORD", "dev-password-12345")


async def seed() -> None:
    if settings.is_production:
        raise RuntimeError("Refusing to seed development data in production.")

    async with async_session_factory() as db:
        existing = (
            await db.execute(select(User).where(User.email == DEV_USER_EMAIL))
        ).scalar_one_or_none()
        if existing:
            print(f"Dev user already exists: {DEV_USER_EMAIL}")
            return

        user = User(
            email=DEV_USER_EMAIL,
            password_hash=hash_password(DEV_USER_PASSWORD),
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()

        db.add(
            BusinessProfile(
                user_id=user.id,
                business_name="Demo Cleaning Co.",
                owner_name="Demo Owner",
                email=DEV_USER_EMAIL,
                country="US",
                currency="USD",
                timezone="America/New_York",
                tax_rate_bps=0,
            )
        )
        db.add(
            Customer(
                user_id=user.id,
                name="Sample Customer",
                email="customer@example.com",
                phone="555-0100",
            )
        )
        await db.commit()
    print(f"Seeded dev user {DEV_USER_EMAIL}. Change the password before any real use.")


if __name__ == "__main__":
    asyncio.run(seed())
