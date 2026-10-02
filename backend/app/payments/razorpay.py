"""Razorpay subscription integration."""
from __future__ import annotations
import hashlib
import hmac
from typing import Any
import httpx
from app.core.config import settings

BASE_URL = "https://api.razorpay.com/v1"
PLAN_TO_ID = {
    "starter": lambda: settings.razorpay_starter_plan_id,
    "pro": lambda: settings.razorpay_pro_plan_id,
    "business": lambda: settings.razorpay_business_plan_id,
}

def _auth() -> tuple[str, str]:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise ValueError("Razorpay credentials are not configured.")
    return settings.razorpay_key_id, settings.razorpay_key_secret

def _request(method: str, path: str, **kwargs: Any) -> dict:
    with httpx.Client(timeout=settings.razorpay_api_timeout_seconds) as client:
        response = client.request(method, f"{BASE_URL}{path}", auth=_auth(),
                                  headers={"Content-Type": "application/json"}, **kwargs)
    if response.is_error:
        detail = response.text[:500].replace("\n", " ")
        raise RuntimeError(f"Razorpay API returned HTTP {response.status_code}: {detail}")
    return response.json()

def create_subscription(user_id: int, email: str, plan: str) -> dict:
    plan_id = PLAN_TO_ID[plan]()
    if not plan_id:
        raise ValueError(f"Razorpay plan ID for '{plan}' is not configured.")
    data = _request("POST", "/subscriptions", json={
        "plan_id": plan_id,
        "total_count": settings.razorpay_total_count,
        "customer_notify": 1,
        "notes": {"quoteflow_user_id": str(user_id), "quoteflow_plan": plan, "quoteflow_email": email[:200]},
    })
    if not data.get("id"):
        raise RuntimeError("Razorpay did not return a subscription ID.")
    return data

def cancel_subscription(subscription_id: str) -> dict:
    return _request("POST", f"/subscriptions/{subscription_id}/cancel", json={"cancel_at_cycle_end": 1})

def fetch_subscription(subscription_id: str) -> dict:
    return _request("GET", f"/subscriptions/{subscription_id}")

def verify_checkout_signature(subscription_id: str, payment_id: str, signature: str) -> bool:
    message = f"{subscription_id}|{payment_id}".encode()
    expected = hmac.new(settings.razorpay_key_secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()

def plan_from_plan_id(plan_id: str | None) -> str:
    if not plan_id:
        return ""
    for plan, getter in PLAN_TO_ID.items():
        if plan_id == getter():
            return plan
    return ""
