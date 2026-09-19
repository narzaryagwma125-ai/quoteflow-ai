"""Public contact form endpoint: validates, rate-limits, and emails support."""

from __future__ import annotations

import logging
from html import escape

from fastapi import APIRouter, Request

from app.api.deps import verify_origin
from app.core.config import settings
from app.core.errors import service_unavailable
from app.schemas.auth import MessageResponse
from app.schemas.contact import ContactRequest
from app.security.rate_limit import client_ip_key, enforce
from app.services.email import send_email

logger = logging.getLogger("quoteflow.contact")

router = APIRouter(prefix="/api/contact", tags=["contact"])

CONTACT_RATE_LIMIT = 3
CONTACT_RATE_WINDOW_SECONDS = 3600

SENT_MESSAGE = (
    "Thank you! Your message has been sent. We typically reply within 1-2 business days."
)


def _contact_email_body(payload: ContactRequest) -> tuple[str, str]:
    text = (
        "New contact form submission\n\n"
        f"Name: {payload.name}\n"
        f"Email: {payload.email}\n"
        f"Subject: {payload.subject}\n\n"
        f"{payload.message}\n"
    )
    name = escape(payload.name)
    email = escape(payload.email)
    subject = escape(payload.subject)
    message = escape(payload.message).replace("\n", "<br/>")
    html = (
        "<h3>New contact form submission</h3>"
        f"<p><strong>Name:</strong> {name}<br/>"
        f"<strong>Email:</strong> <a href=\"mailto:{email}\">{email}</a><br/>"
        f"<strong>Subject:</strong> {subject}</p>"
        "<hr/>"
        f"<p>{message}</p>"
    )
    return text, html


@router.post("", response_model=MessageResponse)
async def submit_contact(payload: ContactRequest, request: Request) -> MessageResponse:
    verify_origin(request)
    await enforce(
        client_ip_key(request),
        "contact",
        limit=CONTACT_RATE_LIMIT,
        window_seconds=CONTACT_RATE_WINDOW_SECONDS,
    )

    # Honeypot: bots that fill the hidden field are dropped without any signal.
    if payload.website:
        logger.info("CONTACT_SPAM_DROPPED from=%s", payload.email)
        return MessageResponse(message=SENT_MESSAGE)

    try:
        await send_email(
            settings.support_email,
            f"[QuoteFlow Support] {payload.subject}",
            *_contact_email_body(payload),
        )
    except Exception:
        logger.exception("CONTACT_EMAIL_FAILED from=%s subject=%r", payload.email, payload.subject)
        raise service_unavailable(
            "Could not deliver your message right now. Please try again in a moment."
        )

    logger.info("CONTACT_SUBMITTED from=%s subject=%r", payload.email, payload.subject)
    return MessageResponse(message=SENT_MESSAGE)