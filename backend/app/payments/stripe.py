"""Stripe Checkout + Webhook signature verification.

Card numbers, CVV, and bank details are never collected or stored by this app.
"""

from __future__ import annotations

import hashlib

import stripe

from app.core.config import settings

# Map internal plans to configured Stripe price IDs. Never accept price IDs from the frontend.
PLAN_TO_PRICE_ID = {
    "starter": lambda: settings.stripe_starter_price_id,
    "business": lambda: settings.stripe_business_price_id,
}


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
