from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class MeResponse(BaseModel):
    id: int
    email: str
    is_email_verified: bool
    plan: Literal["free", "starter", "pro", "business"] = "free"
    subscription_status: str = "none"
    has_business_profile: bool = False
    trial_active: bool = False
    trial_expired: bool = False
    trial_days_remaining: int = 0
    trial_expires_at: datetime | None = None
    trial_unlimited: bool = False


class AccountUpdateRequest(BaseModel):
    email: EmailStr | None = None
