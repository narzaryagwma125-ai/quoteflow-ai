"""Transactional email delivery.

Primary transport is Resend's HTTPS Email API so the backend does not depend on
outbound SMTP ports that may be blocked by managed hosting providers.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("quoteflow.email")


async def _send_via_resend(
    to_email: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> None:
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    if not settings.email_from or "@quoteflow.example" in settings.email_from:
        raise RuntimeError("EMAIL_FROM must be set to a verified Resend sender")

    payload = {
        "from": settings.email_from,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html

    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=settings.email_api_timeout_seconds) as client:
        response = await client.post(
            settings.resend_api_url,
            headers=headers,
            json=payload,
        )

    if response.is_error:
        # Never log the API key or email body. Resend's response is useful for
        # diagnosis but may contain provider metadata, so keep it bounded.
        detail = response.text[:500].replace("\n", " ")
        raise RuntimeError(
            f"Resend email API returned HTTP {response.status_code}: {detail}"
        )

    logger.info("EMAIL_SENT provider=resend subject=%r to=%r", subject, to_email)


async def send_email(to_email: str, subject: str, text: str, html: str | None = None) -> None:
    """Send a transactional email over HTTPS.

    SMTP settings are intentionally no longer used by the production path.
    This avoids Render Free's blocked SMTP ports (25/465/587).
    """
    await _send_via_resend(to_email, subject, text, html)


def verification_email_body(link: str) -> tuple[str, str]:
    text = (
        "Welcome to QuoteFlow AI!\n\n"
        "Please verify your email address to activate your account:\n"
        f"{link}\n\n"
        "If you did not create this account, you can safely ignore this email.\n"
    )
    html = (
        "<p>Welcome to QuoteFlow AI!</p>"
        "<p>Please verify your email address to activate your account:</p>"
        f'<p><a href="{link}">Verify my email</a></p>'
        "<p>If you did not create this account, you can safely ignore this email.</p>"
    )
    return text, html


def password_reset_email_body(link: str) -> tuple[str, str]:
    text = (
        "We received a request to reset your QuoteFlow AI password.\n\n"
        f"Reset your password here (expires in 30 minutes):\n{link}\n\n"
        "If you did not request this, you can safely ignore this email."
    )
    html = (
        "<p>We received a request to reset your QuoteFlow AI password.</p>"
        "<p>This link expires in 30 minutes.</p>"
        f'<p><a href="{link}">Reset my password</a></p>'
        "<p>If you did not request this, you can safely ignore this email.</p>"
    )
    return text, html


def quote_response_email_body(business_email: str, quote_number: str, name: str, approved: bool) -> str:
    verb = "accepted" if approved else "declined"
    return (
        f"Good news — {name} has {verb} quote {quote_number}. "
        "Sign in to QuoteFlow AI to see the details."
    )
