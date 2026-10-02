"""Monthly usage counters (quotes, AI) per user."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import UsageCounter


def current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


async def increment_usage(db: AsyncSession, user_id: int, feature: str, by: int = 1) -> None:
    """Increment the monthly counter (portable upsert for SQLite + PostgreSQL)."""
    period = current_period()
    result = await db.execute(
        select(UsageCounter).where(
            UsageCounter.user_id == user_id,
            UsageCounter.feature == feature,
            UsageCounter.period == period,
        )
    )
    counter = result.scalar_one_or_none()
    if counter is None:
        db.add(UsageCounter(user_id=user_id, feature=feature, period=period, count=by))
        await db.flush()
    else:
        counter.count += by
        await db.flush()


async def get_usage(db: AsyncSession, user_id: int, feature: str) -> int:
    result = await db.execute(
        select(UsageCounter.count).where(
            UsageCounter.user_id == user_id,
            UsageCounter.feature == feature,
            UsageCounter.period == current_period(),
        )
    )
    return result.scalar_one_or_none() or 0
