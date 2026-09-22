"""Public (customer-facing) quote links. No auth required, token-based access.

Security:
- tokens are high-entropy and only stored hashed in the DB
- explicit expiry + owner revocation
- rate limited, no indexing headers
- private fields (customer notes, audit info) are never exposed
- accept/reject are CSRF-protected state-changing actions with confirmation handled client-side
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, not_found, service_unavailable
from app.db.session import get_db
from app.models.business_profile import BusinessProfile
from app.models.customer import Customer
from app.models.quote import Quote
from app.schemas.public import (
    PublicQuoteItem,
    PublicQuoteRespond,
    PublicQuoteResponse,
)
from app.security.csrf import require_csrf, set_csrf_cookie
from app.security.rate_limit import client_ip_key, enforce
from app.security.tokens import hash_token
from app.services import docx_to_pdf
from app.services.audit import audit
from app.services.email import quote_response_email_body, send_email
from app.services.pdf_render import render_quote_pdf

router = APIRouter(prefix="/api/public/quotes", tags=["public-quotes"])

RESPOND_INELIGIBLE = ("draft", "expired", "cancelled")
RESPOND_DONE = ("accepted", "rejected")


async def _resolve_token(db: AsyncSession, token: str) -> Quote:
    result = await db.execute(
        select(Quote).where(Quote.public_token_hash == hash_token(token))
    )
    quote = result.scalar_one_or_none()
    if quote is None:
        raise not_found("This quote link is invalid or has been revoked.")
    if quote.public_token_expires_at is not None:
        expiry = quote.public_token_expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry <= datetime.now(UTC):
            quote.status = "expired"
            await db.commit()
            raise not_found("This quote link has expired.")
    if quote.status == "sent":
        quote.status = "viewed"
        await db.commit()
    return quote


@router.get("/{token}", response_model=PublicQuoteResponse)
async def get_public_quote(
    token: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> PublicQuoteResponse:
    await enforce(client_ip_key(request), "public_quote_view", limit=60, window_seconds=3600)
    # Set a double-submit CSRF cookie so the Accept/Reject forms can submit safely.
    set_csrf_cookie(response, request)
    quote = await _resolve_token(db, token)

    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == quote.user_id))
    ).scalar_one_or_none()

    items = [
        PublicQuoteItem(
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price_minor=item.unit_price_minor,
            line_total_minor=item.line_total_minor,
        )
        for item in quote.items
    ]

    return PublicQuoteResponse(
        business_name=profile.business_name if profile else "",
        quote_number=quote.quote_number,
        status=quote.status,
        issue_date=quote.issue_date,
        expiry_date=quote.expiry_date,
        currency=quote.currency,
        subtotal_minor=quote.subtotal_minor,
        discount_minor=quote.discount_minor,
        tax_minor=quote.tax_minor,
        total_minor=quote.total_minor,
        notes=quote.notes,
        terms=quote.terms,
        items=items,
        may_respond=quote.status not in RESPOND_DONE and quote.status not in RESPOND_INELIGIBLE,
    )


async def _respond(request: Request, token: str, payload: PublicQuoteRespond, accept: bool, db: AsyncSession) -> dict:
    await enforce(client_ip_key(request), "public_quote_respond", limit=5, window_seconds=3600)
    require_csrf(request)

    quote = await _resolve_token(db, token)
    if quote.status in RESPOND_DONE:
        raise bad_request(f"This quote has already been {quote.status}.")
    if quote.status in RESPOND_INELIGIBLE:
        raise bad_request("This quote is not open for responses.")

    quote.status = "accepted" if accept else "rejected"
    quote.responded_by_name = payload.name
    quote.responded_by_email = payload.email or ""
    quote.responded_at = datetime.now(UTC)

    # Notify the business owner (safe metadata only)
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == quote.user_id))
    ).scalar_one_or_none()
    if profile:
        await send_email(
            profile.email,
            f"Quote {quote.quote_number} was {'accepted' if accept else 'declined'}",
            quote_response_email_body(profile.email, quote.quote_number, payload.name, accept),
        )

    await audit(
        db,
        "quote.public_responded" if accept else "quote.public_declined",
        user_id=quote.user_id,
        entity_type="quote",
        entity_id=quote.id,
        ip=client_ip_key(request),
    )
    await db.commit()
    return {
        "message": f"Quote {'accepted' if accept else 'declined'}.",
        "quote_number": quote.quote_number,
        "status": quote.status,
    }


@router.post("/{token}/accept")
async def accept_quote(
    token: str,
    payload: PublicQuoteRespond,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _respond(request, token, payload, accept=True, db=db)


@router.post("/{token}/reject")
async def reject_quote(
    token: str,
    payload: PublicQuoteRespond,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _respond(request, token, payload, accept=False, db=db)


@router.get("/{token}/pdf")
async def download_accepted_quote_pdf(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the accepted quote as a PDF, secured by the public token only.

    The quote is always resolved through its high-entropy public token hash —
    never through the quote ID — so this works without any customer login.
    The download is only available after the customer has accepted the quote
    and uses the exact accepted quote data and the business's custom template
    when one is configured.
    """
    await enforce(client_ip_key(request), "public_quote_pdf", limit=10, window_seconds=3600)
    quote = await _resolve_token(db, token)

    if quote.status != "accepted":
        raise bad_request("The accepted-quote PDF is only available after the quote is accepted.")

    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == quote.user_id))
    ).scalar_one_or_none()
    customer = await db.get(Customer, quote.customer_id) if quote.customer_id else None
    tax_rate_percent = str(((profile.tax_rate_bps if profile else 0) or 0) / 100)

    try:
        pdf_bytes, _ = render_quote_pdf(
            profile=profile,
            quote=quote,
            customer=customer,
            tax_rate_percent=tax_rate_percent,
        )
    except docx_to_pdf.DocxConversionUnavailable:
        raise service_unavailable(
            "DOCX-to-PDF conversion requires LibreOffice to be installed on the server. "
            "Use the default QuoteFlow template while it is unavailable."
        ) from None

    await audit(
        db,
        "quote.accepted_pdf_downloaded",
        user_id=quote.user_id,
        entity_type="quote",
        entity_id=quote.id,
        ip=client_ip_key(request),
    )
    await db.commit()

    safe_filename = f"{quote.quote_number}-Accepted.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
