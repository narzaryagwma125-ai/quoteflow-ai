"""Stripe Checkout + Webhook signature verification.

Card numbers, CVV, and bank details are never collected or stored by this app.
"""

from __future__ import annotations

import hashlib

import stripe

from app.core.config import settings

# Map internal plans to configured Stripe price IDs. Never accept price IDs from the frontend.
PLAN_TO_PRICE_ID = {
    # Customer-facing name is Basic; the internal key remains `starter` for DB compatibility.
    "starter": lambda: settings.stripe_starter_price_id,
    "pro": lambda: settings.stripe_pro_price_id,
    "business": lambda: settings.stripe_business_price_id,
}

# Required monthly USD prices in cents. These are checked against Stripe at checkout
# so a misconfigured Price ID cannot silently charge the wrong plan amount.
PLAN_PRICING = {
    "starter": {"label": "Basic", "amount": 600, "currency": "usd", "interval": "month"},
    "pro": {"label": "Pro", "amount": 1200, "currency": "usd", "interval": "month"},
    "business": {"label": "Business", "amount": 2400, "currency": "usd", "interval": "month"},
}


def plan_from_price_id(price_id: str | None) -> str:
    """Map a configured Stripe price ID to an internal plan name."""
    if price_id and price_id == settings.stripe_starter_price_id:
        return "starter"
    if price_id and price_id == settings.stripe_pro_price_id:
        return "pro"
    if price_id and price_id == settings.stripe_business_price_id:
        return "business"
    return ""


def validate_stripe_price_for_plan(plan: str, price_id: str) -> None:
    """Fail closed when a Stripe Price ID does not match the configured plan price.

    This prevents an environment-variable mistake such as assigning the Basic $6
    Price ID to STRIPE_PRO_PRICE_ID from charging the wrong amount.
    """
    expected = PLAN_PRICING.get(plan)
    if not expected:
        raise ValueError(f"Unknown plan '{plan}'.")
    if not price_id:
        raise ValueError(f"Stripe price ID for plan '{plan}' is not configured.")

    configured_ids = [
        settings.stripe_starter_price_id,
        settings.stripe_pro_price_id,
        settings.stripe_business_price_id,
    ]
    if len(set(configured_ids)) != len(configured_ids):
        raise ValueError("Stripe plan Price IDs must be unique across Basic, Pro, and Business.")

    try:
        remote = stripe.Price.retrieve(price_id)
    except stripe.error.StripeError as exc:
        raise ValueError(f"Unable to validate Stripe price for {expected['label']}.") from exc

    def get_value(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    if get_value(remote, "id") != price_id:
        raise ValueError(f"Stripe Price ID validation failed for {expected['label']}.")
    if get_value(remote, "active") is not True:
        raise ValueError(f"Stripe price for {expected['label']} is not active.")
    if get_value(remote, "unit_amount") != expected["amount"]:
        raise ValueError(
            f"Stripe price mismatch for {expected['label']}: expected ${expected['amount'] / 100:.0f}/month."
        )
    if str(get_value(remote, "currency", "")).lower() != expected["currency"]:
        raise ValueError(f"Stripe currency mismatch for {expected['label']}: expected USD.")

    recurring = get_value(remote, "recurring") or {}
    interval = get_value(recurring, "interval")
    if interval != expected["interval"]:
        raise ValueError(f"Stripe billing interval mismatch for {expected['label']}: expected monthly.")


def get_stripe_client() -> stripe.StripeClient:
    stripe.api_key = settings.stripe_secret_key
    return stripe


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> object:
    """Verify a Stripe webhook signature and return the parsed event.

    Raises stripe.SignatureVerificationError on invalid signatures.
    """
    get_stripe_client()
    return stripe.Webhook.construct_event(
        raw_body, signature_header, settings.stripe_webhook_secret
    )


def create_checkout_session(
    user_id: int,
    email: str,
    plan: str,
    metadata: dict | None = None,
) -> dict:
    """Create a Stripe Checkout Session for a subscription.

    The authenticated user ID is placed in metadata so webhooks can map
    the subscription back to the account. activation happens ONLY via webhook.
    """
    get_stripe_client()
    price_id = PLAN_TO_PRICE_ID[plan]()
    if not price_id:
        raise ValueError(f"Stripe price ID for plan '{plan}' is not configured.")
    validate_stripe_price_for_plan(plan, price_id)

    meta = dict(metadata or {})
    meta["quoteflow_user_id"] = str(user_id)
    meta["quoteflow_plan"] = plan

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=email,
        client_reference_id=str(user_id),
        metadata=meta,
        subscription_data={"metadata": meta},
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        allow_promotion_codes=True,
    )
    return {"id": session.id, "url": session.url}


def cancel_subscription_at_period_end(subscription_id: str) -> None:
    get_stripe_client()
    stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)


def payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()
