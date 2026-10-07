"""PayPal international checkout using the Orders v2 API.

This module deliberately uses PayPal's standard one-time Orders API.
PayPal's current custom recurring Subscriptions API is restricted to
select partners, so recurring international billing is not assumed here.
"""

from __future__ import annotations

import base64
import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import settings

SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
LIVE_BASE_URL = "https://api-m.paypal.com"

PLAN_PRICES_USD: dict[str, Decimal] = {
    "starter": Decimal("6.00"),
    "pro": Decimal("12.00"),
    "business": Decimal("24.00"),
}


def _base_url() -> str:
    return LIVE_BASE_URL if settings.paypal_mode == "live" else SANDBOX_BASE_URL


def _credentials() -> tuple[str, str]:
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise ValueError("PayPal credentials are not configured.")
    return settings.paypal_client_id, settings.paypal_client_secret


def plan_price_usd(plan: str) -> Decimal:
    try:
        return PLAN_PRICES_USD[plan]
    except KeyError as exc:
        raise ValueError(f"Unsupported PayPal plan: {plan}") from exc


def _request(
    method: str,
    path: str,
    *,
    access_token: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.setdefault("Accept", "application/json")
    headers.setdefault("Content-Type", "application/json")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    with httpx.Client(timeout=settings.paypal_api_timeout_seconds) as client:
        response = client.request(method, f"{_base_url()}{path}", headers=headers, **kwargs)

    if response.is_error:
        detail = response.text[:1000].replace("\n", " ")
        raise RuntimeError(f"PayPal API returned HTTP {response.status_code}: {detail}")

    if not response.content:
        return {}
    return response.json()


def get_access_token() -> str:
    client_id, client_secret = _credentials()
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    with httpx.Client(timeout=settings.paypal_api_timeout_seconds) as client:
        response = client.post(
            f"{_base_url()}/v1/oauth2/token",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en_US",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
            data={"grant_type": "client_credentials"},
        )

    if response.is_error:
        detail = response.text[:1000].replace("\n", " ")
        raise RuntimeError(
            f"PayPal OAuth returned HTTP {response.status_code}: {detail}"
        )

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("PayPal OAuth response did not contain an access token.")
    return str(token)


def create_order(*, user_id: int, plan: str) -> dict[str, Any]:
    amount = plan_price_usd(plan)
    token = get_access_token()

    # custom_id lets the server correlate a completed order with the
    # QuoteFlow account without trusting the browser to identify the user.
    custom_id = f"qf:{user_id}:{plan}"
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "custom_id": custom_id,
                "description": f"QuoteFlow AI {plan.title()} - 30 days",
                "invoice_id": f"QF-{user_id}-{uuid4().hex[:20]}",
                "amount": {
                    "currency_code": "USD",
                    "value": f"{amount:.2f}",
                },
            }
        ],
        "application_context": {
            "brand_name": "QuoteFlow AI",
            "user_action": "PAY_NOW",
            "return_url": settings.paypal_success_url,
            "cancel_url": settings.paypal_cancel_url,
        },
    }

    return _request(
        "POST",
        "/v2/checkout/orders",
        access_token=token,
        headers={"PayPal-Request-Id": uuid4().hex},
        json=payload,
    )


def capture_order(order_id: str) -> dict[str, Any]:
    if not order_id or len(order_id) > 100:
        raise ValueError("Invalid PayPal order ID.")
    token = get_access_token()
    return _request(
        "POST",
        f"/v2/checkout/orders/{order_id}/capture",
        access_token=token,
    )


def get_order(order_id: str) -> dict[str, Any]:
    if not order_id or len(order_id) > 100:
        raise ValueError("Invalid PayPal order ID.")
    token = get_access_token()
    return _request("GET", f"/v2/checkout/orders/{order_id}", access_token=token)


def validate_captured_order(
    order: dict[str, Any],
    *,
    user_id: int,
    plan: str,
) -> tuple[bool, str]:
    if order.get("status") != "COMPLETED":
        return False, "PayPal order is not completed."

    units = order.get("purchase_units") or []
    if len(units) != 1:
        return False, "Unexpected PayPal purchase unit."

    unit = units[0]
    expected_custom_id = f"qf:{user_id}:{plan}"

    captures = ((unit.get("payments") or {}).get("captures") or [])
    if len(captures) != 1:
        return False, "Unexpected PayPal capture."

    custom_id = captures[0].get("custom_id")
    if custom_id != expected_custom_id:
        return False, "PayPal order does not belong to this checkout."

    amount = ((unit.get("amount") or {}).get("value") or "")
    currency = ((unit.get("amount") or {}).get("currency_code") or "")

    try:
        actual = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return False, "Invalid PayPal amount."

    if currency != "USD" or actual != plan_price_usd(plan):
        return False, "PayPal amount or currency does not match the selected plan."

    return True, ""

def verify_webhook_signature(
    *,
    transmission_id: str,
    transmission_time: str,
    cert_url: str,
    auth_algo: str,
    transmission_sig: str,
    webhook_id: str,
    webhook_event: dict[str, Any],
) -> bool:
    """Verify a PayPal webhook using PayPal's webhook verification endpoint."""
    token = get_access_token()
    payload = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": webhook_id,
        "webhook_event": webhook_event,
    }
    result = _request(
        "POST",
        "/v1/notifications/verify-webhook-signature",
        access_token=token,
        json=payload,
    )
    return result.get("verification_status") == "SUCCESS"


def payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()



