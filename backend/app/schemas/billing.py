from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    plan: Literal["starter", "business"]


class CheckoutResponse(BaseModel):
    url: str


class SubscriptionPublic(BaseModel):
    plan: Literal["free", "starter", "business"]
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    quotes_used: int = 0
    quotes_limit: int | None = 0
    quotes_remaining: int | None = 0
    ai_used: int = 0
    ai_limit: int = 0
    ai_remaining: int = 0
    trial_active: bool = False
    trial_expired: bool = False
    trial_days_remaining: int = 0
    trial_expires_at: datetime | None = None
    trial_unlimited: bool = False


class CancelSubscriptionResponse(BaseModel):
    plan: str
    status: str
    cancel_at_period_end: bool = True
