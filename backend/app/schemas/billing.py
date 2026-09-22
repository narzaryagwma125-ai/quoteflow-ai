from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

class CheckoutRequest(BaseModel):
    plan: Literal["starter", "pro", "business"]

class CheckoutResponse(BaseModel):
    key_id: str
    subscription_id: str
    name: str = "QuoteFlow AI"
    description: str = "QuoteFlow AI subscription"
    prefill_email: str

class PaymentVerifyRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str

class SubscriptionPublic(BaseModel):
    plan: Literal["free", "starter", "pro", "business"]
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    quotes_used: int = 0
    quotes_limit: int | None = 0
    quotes_remaining: int | None = 0
    ai_used: int = 0
    ai_limit: int | None = 0
    ai_remaining: int | None = 0
    trial_active: bool = False
    trial_expired: bool = False
    trial_days_remaining: int = 0
    trial_expires_at: datetime | None = None
    trial_unlimited: bool = False

class CancelSubscriptionResponse(BaseModel):
    plan: str
    status: str
    cancel_at_period_end: bool = True
