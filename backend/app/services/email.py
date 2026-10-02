"""Transactional email delivery via Brevo SMTP."""
from __future__ import annotations
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from app.core.config import settings
logger = logging.getLogger("quoteflow.email")

def _send_smtp(to_email: str, subject: str, text: str, html: str | None = None) -> None:
    if not settings.smtp_username or not settings.smtp_password:
        raise RuntimeError("SMTP_USERNAME/SMTP_PASSWORD are not configured")
    if not settings.email_from or "@quoteflow.example" in settings.email_from:
        raise RuntimeError("EMAIL_FROM must be set to a verified sender")
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
        smtp.ehlo(); smtp.starttls(); smtp.ehlo()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)
    logger.info("EMAIL_SENT provider=brevo_smtp subject=%r to=%r", subject, to_email)

async def send_email(to_email: str, subject: str, text: str, html: str | None = None) -> None:
    await asyncio.to_thread(_send_smtp, to_email, subject, text, html)


def _is_configured() -> bool:
    return bool(settings.smtp_username and settings.smtp_password)


async def deliver_best_effort(
    sender,
    to_email: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    """Send a non-critical email, logging instead of raising on failure.

    Verification, password-reset and quote-response messages are notifications
    about a request that has *already* succeeded. Letting a missing or
    unreachable mail provider raise here turns a successful signup or a
    customer's quote acceptance into a 5xx, which is worse than a missing
    notification. Returns ``True`` when the message was handed to the provider.

    ``sender`` is passed in so callers keep control over which function is
    used (and so it stays easy to substitute in tests).
    """
    try:
        await sender(to_email, subject, text, html)
    except Exception:
        if _is_configured():
            logger.exception("EMAIL_FAILED subject=%r to=%r", subject, to_email)
        else:
            # A missing provider is a configuration gap, not an incident — log
            # the message locally so local development stays usable.
            logger.warning(
                "EMAIL_NOT_SENT (SMTP not configured) subject=%r to=%r", subject, to_email
            )
            if not settings.is_production:
                logger.info(
                    "EMAIL_CONSOLE_FALLBACK subject=%r to=%r\n%s", subject, to_email, text
                )
        return False
    return True

def verification_email_body(link: str) -> tuple[str, str]:
    text = ("Welcome to QuoteFlow AI!\n\nPlease verify your email address to activate your account:\n"
            f"{link}\n\nIf you did not create this account, you can safely ignore this email.\n")
    html = ("<p>Welcome to QuoteFlow AI!</p><p>Please verify your email address to activate your account:</p>"
            f'<p><a href="{link}">Verify my email</a></p>'
            "<p>If you did not create this account, you can safely ignore this email.</p>")
    return text, html

def password_reset_email_body(link: str) -> tuple[str, str]:
    text = ("We received a request to reset your QuoteFlow AI password.\n\n"
            f"Reset your password here (expires in 30 minutes):\n{link}\n\n"
            "If you did not request this, you can safely ignore this email.")
    html = ("<p>We received a request to reset your QuoteFlow AI password.</p><p>This link expires in 30 minutes.</p>"
            f'<p><a href="{link}">Reset my password</a></p>'
            "<p>If you did not request this, you can safely ignore this email.</p>")
    return text, html

def quote_response_email_body(business_email: str, quote_number: str, name: str, approved: bool) -> str:
    verb = "accepted" if approved else "declined"
    return f"Good news — {name} has {verb} quote {quote_number}. Sign in to QuoteFlow AI to see the details."
