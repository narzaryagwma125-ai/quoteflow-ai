"""Subscription plan definitions, limits, and feature enforcement.

Do NOT trust subscription status reported by the frontend. The backend derives
the effective plan from Razorpay webhooks + the local Subscription row.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import payment_required
from app.models.subscription import Subscription
from app.models.user import User
from app.services.usage import get_usage

ACTIVE_STATUSES = {"active", "trialing"}


@dataclass(frozen=True)
class Plan:
    name: str
    quote_monthly_limit: int | None  # None = unlimited
    ai_monthly_limit: int | None
    customers_limit: int | None  # None = unlimited
    secure_links: bool
    reminders: bool
    advanced_dashboard: bool


PLANS: dict[str, Plan] = {
    "free": Plan(
        name="free",
        quote_monthly_limit=3,
        ai_monthly_limit=10,
        customers_limit=25,
        secure_links=True,
        reminders=False,
        advanced_dashboard=False,
    ),
    "starter": Plan(
        name="starter",
        quote_monthly_limit=200,
        ai_monthly_limit=200,
        customers_limit=None,
        secure_links=True,
        reminders=True,
        advanced_dashboard=False,
    ),
    "pro": Plan(
        name="pro",
        quote_monthly_limit=1000,
        ai_monthly_limit=1000,
        customers_limit=None,
        secure_links=True,
        reminders=True,
        advanced_dashboard=True,
    ),
    "business": Plan(
        name="business",
        quote_monthly_limit=None,
        ai_monthly_limit=None,
        customers_limit=None,
        secure_links=True,
        reminders=True,
        advanced_dashboard=True,
    ),
}


class NotSubscribedError(Exception):
    pass


def trial_expires_at(user: User) -> datetime | None:
    """Free-trial expiry computed from the user's actual signup timestamp.

    Returns None when the trial is disabled or the signup date is missing or
    invalid so the caller can fall back to normal plan limits safely.
    """
    if not settings.free_trial_enabled:
        return None
    created_at = getattr(user, "created_at", None)
    if created_at is None or not isinstance(created_at, datetime):
        return None
    try:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return created_at + timedelta(days=settings.free_trial_days)
    except (TypeError, OverflowError, ValueError):
        return None


def trial_status(user: User) -> dict[str, Any]:
    """Free-trial status derived from created_at, safe for any timezone input.

    Always uses UTC for comparisons so the expiry is unambiguous regardless of
    where the signup timestamp was produced.
    """
    expiry = trial_expires_at(user)
    if expiry is None:
        return {
            "trial_active": False,
            "trial_expired": False,
            "trial_days_remaining": 0,
            "trial_expires_at": None,
            "trial_unlimited": False,
        }
    now = datetime.now(UTC)
    if now >= expiry:
        return {
            "trial_active": False,
            "trial_expired": True,
            "trial_days_remaining": 0,
            "trial_expires_at": expiry,
            "trial_unlimited": False,
        }
    days_remaining = max(1, math.ceil((expiry - now).total_seconds() / 86400))
    return {
        "trial_active": True,
        "trial_expired": False,
        "trial_days_remaining": days_remaining,
        "trial_expires_at": expiry,
        "trial_unlimited": settings.free_trial_unlimited,
    }


async def get_subscription(db: AsyncSession, user_id: int) -> Subscription | None:
    # Prefer a currently usable paid subscription over a newer incomplete/canceled
    # checkout attempt. Razorpay can deliver multiple subscription events for the
    # same user, and an abandoned checkout must never hide an active plan.
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(
            Subscription.status.in_(ACTIVE_STATUSES).desc(),
            Subscription.id.desc(),
        )
    )
    return result.scalars().first()


def effective_plan(subscription: Subscription | None) -> str:
    """Effective plan name given subscription row.

    Free users / expired / non-active subscriptions fall back to 'free'.
    """
    if subscription is None:
        return "free"
    if subscription.status not in ACTIVE_STATUSES:
        return "free"
    return subscription.plan if subscription.plan in PLANS else "free"


async def current_plan(db: AsyncSession, user_id: int) -> tuple[str, Subscription | None]:
    subscription = await get_subscription(db, user_id)
    return effective_plan(subscription), subscription


async def require_plan_feature(
    db: AsyncSession, user_: User, feature: str
) -> Subscription | None:
    """Raise 402 if the user's effective plan does not allow `feature`.

    Returns the subscription row (or None for free) for callers that need it.
    """
    subscription = await get_subscription(db, user_.id)
    plan_name = effective_plan(subscription)
    plan = PLANS[plan_name]
    trial = trial_status(user_)

    if feature == "quotes":
        if settings.dev_ignore_quote_limits and settings.app_env == "development":
            return subscription
        limit = plan.quote_monthly_limit
        if trial["trial_active"] and plan_name == "free":
            # Unsubscribed users on an active free trial get Starter-level limits.
            limit = PLANS["starter"].quote_monthly_limit
        if limit is not None:
            used = await get_usage(db, user_.id, "quotes")
            if used >= limit:
                suffix = "upgrade to increase your monthly limit" if plan_name != "business" else "limit reached"
                raise payment_required(
                    f"Monthly quote limit reached ({limit}). Please {suffix}."
                )
    elif feature == "ai":
        limit = plan.ai_monthly_limit
        if trial["trial_active"] and plan_name == "free":
            limit = PLANS["starter"].ai_monthly_limit
        if limit is not None:
            used = await get_usage(db, user_.id, "ai")
            if used >= limit:
                raise payment_required("Monthly AI usage limit reached. Upgrade your plan for more.")
    elif feature == "reminders":
        if not plan.reminders:
            raise payment_required("Quote reminders require the Starter plan or higher.")
    elif feature == "advanced_dashboard":
        if not plan.advanced_dashboard:
            raise payment_required("Advanced dashboard requires the Business plan.")
    return subscription


async def get_usage_summary(db: AsyncSession, user: User) -> dict:
    subscription = await get_subscription(db, user.id)
    plan_name = effective_plan(subscription)
    plan = PLANS[plan_name]
    trial = trial_status(user)
    quotes_used = await get_usage(db, user.id, "quotes")
    ai_used = await get_usage(db, user.id, "ai")

    quotes_limit = plan.quote_monthly_limit
    ai_limit = plan.ai_monthly_limit
    customers_limit = plan.customers_limit
    if trial["trial_active"] and plan_name == "free":
        quotes_limit = PLANS["starter"].quote_monthly_limit
        ai_limit = PLANS["starter"].ai_monthly_limit
        customers_limit = PLANS["starter"].customers_limit

    return {
        "plan": plan_name,
        "status": subscription.status if subscription else plan_name,
        "current_period_start": subscription.current_period_start if subscription else None,
        "current_period_end": subscription.current_period_end if subscription else None,
        "cancel_at_period_end": subscription.cancel_at_period_end if subscription else False,
        "quotes_used": quotes_used,
        "quotes_limit": quotes_limit,
        "quotes_remaining": None if quotes_limit is None else max(0, quotes_limit - quotes_used),
        "ai_used": ai_used,
        "ai_limit": ai_limit,
        "ai_remaining": None if ai_limit is None else max(0, ai_limit - ai_used),
        "customers_limit": customers_limit,
        "reminders_enabled": plan.reminders,
        "advanced_dashboard": plan.advanced_dashboard,
        "trial_active": trial["trial_active"],
        "trial_expired": trial["trial_expired"],
        "trial_days_remaining": trial["trial_days_remaining"],
        "trial_expires_at": trial["trial_expires_at"],
        "trial_unlimited": trial["trial_unlimited"],
    }
