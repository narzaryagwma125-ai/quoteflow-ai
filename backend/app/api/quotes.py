from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, pagination_params, require_quotes, verify_origin
from app.core.config import settings
from app.core.errors import bad_request, not_found, service_unavailable
from app.db.session import get_db
from app.models.business_profile import BusinessProfile
from app.models.customer import Customer
from app.models.quote import Quote
from app.models.user import User
from app.schemas.quote import (
    CurrencyTotal,
    QuoteCreate,
    QuotePage,
    QuotePublic,
    QuoteResponse,
    QuoteStats,
    QuoteUpdate,
)
from app.security.rate_limit import client_ip_key, enforce
from app.security.tokens import generate_public_quote_token, hash_token
from app.services import docx_to_pdf
from app.services.audit import audit
from app.services.currency import currency_symbol
from app.services.docx_templates import build_sample_docx, fill_docx_template
from app.services.pdf_render import (
    fill_custom_docx,
    quote_docx_values,
    quote_items,
    render_quote_pdf,
)
from app.services.quote_calc import calculate_quote
from app.services.quotes import (
    apply_items_to_quote,
    get_owned_quote,
    next_quote_number,
    serialize_quote,
)
from app.services.usage import increment_usage
from app.uploads.store import DOCX_MIME_TYPE

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

DEFAULT_TOKEN_TTL_DAYS = 30

_TOTAL_EXCLUDED_STATUSES = ("cancelled",)


def _tax_rate_bps(db_profile: BusinessProfile | None) -> int:
    return db_profile.tax_rate_bps if db_profile else 0


async def _build_public(quote: Quote, db: AsyncSession) -> QuotePublic:
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == quote.user_id))
    ).scalar_one_or_none()
    customer_name = ""
    if quote.customer_id:
        customer = await db.get(Customer, quote.customer_id)
        if customer:
            customer_name = customer.name
    return serialize_quote(quote, _tax_rate_bps(profile), customer_name=customer_name)


@router.get("/stats", response_model=QuoteStats)
async def quote_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuoteStats:
    """Dashboard summary: status counts plus amounts grouped per currency.

    Totals are summed in minor units *per currency* — never across currencies.
    Cancelled quotes are counted in the status map but excluded from the money
    totals (their amounts are no longer quotable).
    """
    base = select(func.count(Quote.id)).where(Quote.user_id == user.id)
    counts = {}
    for status in ("draft", "sent", "viewed", "accepted", "rejected", "expired", "cancelled"):
        counts[status] = (
            await db.execute(base.where(Quote.status == status))
        ).scalar_one() or 0
    total = (await db.execute(base)).scalar_one() or 0

    month_start = date(datetime.now(UTC).year, datetime.now(UTC).month, 1)
    created_this_month = (
        await db.execute(
            base.where(Quote.created_at >= datetime.combine(month_start, datetime.min.time(), tzinfo=UTC))
        )
    ).scalar_one() or 0

    grouped = (
        await db.execute(
            select(
                Quote.currency,
                func.count(Quote.id),
                func.coalesce(func.sum(Quote.subtotal_minor), 0),
                func.coalesce(func.sum(Quote.discount_minor), 0),
                func.coalesce(func.sum(Quote.tax_minor), 0),
                func.coalesce(func.sum(Quote.total_minor), 0),
            )
            .where(
                Quote.user_id == user.id,
                Quote.status.notin_(_TOTAL_EXCLUDED_STATUSES),
            )
            .group_by(Quote.currency)
            .order_by(Quote.currency)
        )
    ).all()

    totals_by_currency = [
        CurrencyTotal(
            currency=row[0],
            currency_symbol=currency_symbol(row[0]),
            count=row[1],
            subtotal_minor=row[2],
            discount_minor=row[3],
            tax_minor=row[4],
            total_minor=row[5],
        )
        for row in grouped
    ]

    return QuoteStats(
        draft=counts["draft"],
        sent=counts["sent"],
        viewed=counts["viewed"],
        accepted=counts["accepted"],
        rejected=counts["rejected"],
        expired=counts["expired"],
        cancelled=counts["cancelled"],
        total=total,
        created_this_month=created_this_month,
        totals_by_currency=totals_by_currency,
    )


@router.get("", response_model=QuotePage)
async def list_quotes(
    pg: dict = Depends(pagination_params),
    status: str | None = Query(default=None, max_length=20),
    customer_id: int | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotePage:
    page, page_size, q, sort, order = (
        pg["page"],
        pg["page_size"],
        pg["q"],
        pg["sort"],
        pg["order"],
    )
    stmt = select(Quote).where(Quote.user_id == user.id)
    if status:
        stmt = stmt.where(Quote.status == status)
    if customer_id:
        stmt = stmt.where(Quote.customer_id == customer_id)
    if currency:
        stmt = stmt.where(Quote.currency == currency.upper())
    if date_from:
        stmt = stmt.where(Quote.issue_date >= date_from)
    if date_to:
        stmt = stmt.where(Quote.issue_date <= date_to)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.outerjoin(Customer, Customer.id == Quote.customer_id).where(
            or_(
                Quote.quote_number.ilike(pattern),
                Customer.name.ilike(pattern),
                Quote.notes.ilike(pattern),
            )
        )

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one() or 0

    sort_col = {
        "number": Quote.quote_number,
        "issue_date": Quote.issue_date,
        "total": Quote.total_minor,
        "status": Quote.status,
    }.get(sort, Quote.created_at)
    stmt = stmt.order_by(sort_col.asc() if order == "asc" else sort_col.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    quotes = (await db.execute(stmt)).scalars().unique().all()
    return QuotePage(
        items=[await _build_public(q, db) for q in quotes],
        total=total,
    )


@router.post("", response_model=QuoteResponse, status_code=201)
async def create_quote(
    payload: QuoteCreate,
    request: Request,
    user: User = Depends(require_quotes),
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    verify_origin(request)

    # Ownership check on the customer if provided
    if payload.customer_id is not None:
        customer = (
            await db.execute(
                select(Customer).where(
                    Customer.id == payload.customer_id, Customer.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if customer is None:
            raise not_found("Customer not found.")

    # Check that the quote number doesn't collide within the business
    effective_number = payload.quote_number or await next_quote_number(db, user.id)
    existing = (
        await db.execute(
            select(Quote.id).where(
                Quote.user_id == user.id, Quote.quote_number == effective_number
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise bad_request("A quote with this number already exists.")

    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    ).scalar_one_or_none()
    tax_rate_bps = _tax_rate_bps(profile)

    calc = calculate_quote(
        [
            {
                "description": item.description,
                "quantity": str(item.quantity),
                "unit": item.unit,
                "unit_price_minor": item.unit_price_minor,
                "sort_order": item.sort_order or idx,
            }
            for idx, item in enumerate(payload.items)
        ],
        discount_minor=payload.discount_minor,
        tax_rate_bps=tax_rate_bps,
    )

    quote = Quote(
        user_id=user.id,
        customer_id=payload.customer_id,
        quote_number=effective_number,
        status="draft",
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        currency=payload.currency,
        subtotal_minor=calc.subtotal_minor,
        discount_minor=calc.discount_minor,
        tax_minor=calc.tax_minor,
        total_minor=calc.total_minor,
        notes=payload.notes,
        terms=payload.terms,
    )
    db.add(quote)
    await db.flush()
    await apply_items_to_quote(db, quote, payload.items)

    await increment_usage(db, user.id, "quotes")
    await audit(db, "quote.created", user_id=user.id, entity_type="quote", entity_id=quote.id)
    await db.commit()

    public = await _build_public(quote, db)
    return QuoteResponse(quote=public)


@router.get("/{quote_id}", response_model=QuotePublic)
async def get_quote(
    quote_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotePublic:
    quote = await get_owned_quote(db, user.id, quote_id)
    return await _build_public(quote, db)


@router.put("/{quote_id}", response_model=QuotePublic)
async def update_quote(
    quote_id: int,
    payload: QuoteUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotePublic:
    verify_origin(request)
    quote = await get_owned_quote(db, user.id, quote_id)

    if payload.customer_id is not None:
        customer = (
            await db.execute(
                select(Customer).where(
                    Customer.id == payload.customer_id, Customer.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if customer is None:
            raise not_found("Customer not found.")

    if payload.quote_number and payload.quote_number != quote.quote_number:
        existing = (
            await db.execute(
                select(Quote.id).where(
                    Quote.user_id == user.id,
                    Quote.quote_number == payload.quote_number,
                    Quote.id != quote.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise bad_request("A quote with this number already exists.")

    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    ).scalar_one_or_none()
    tax_rate_bps = _tax_rate_bps(profile)

    if payload.quote_number is not None:
        quote.quote_number = payload.quote_number
    if payload.customer_id is not None:
        quote.customer_id = payload.customer_id
    if payload.issue_date:
        quote.issue_date = payload.issue_date
    if payload.expiry_date is not None:
        quote.expiry_date = payload.expiry_date
    if payload.currency:
        quote.currency = payload.currency
    if payload.notes is not None:
        quote.notes = payload.notes
    if payload.terms is not None:
        quote.terms = payload.terms

    discount_minor = quote.discount_minor
    if payload.discount is not None:
        discount_minor = payload.discount_minor

    items_payload = payload.items
    if items_payload is not None:
        calc_payload = [
            {
                "description": item.description,
                "quantity": str(item.quantity),
                "unit": item.unit,
                "unit_price_minor": item.unit_price_minor,
                "sort_order": item.sort_order or idx,
            }
            for idx, item in enumerate(items_payload)
        ]
    else:
        calc_payload = [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price_minor": item.unit_price_minor,
                "sort_order": item.sort_order,
            }
            for item in quote.items
        ]

    calc = calculate_quote(calc_payload, discount_minor=discount_minor, tax_rate_bps=tax_rate_bps)
    quote.subtotal_minor = calc.subtotal_minor
    quote.discount_minor = calc.discount_minor
    quote.tax_minor = calc.tax_minor
    quote.total_minor = calc.total_minor

    if items_payload is not None:
        await apply_items_to_quote(db, quote, items_payload)

    # Batch status reset: edits return the quote to draft unless sent
    if quote.status in ("viewed", "accepted", "rejected", "expired", "cancelled"):
        quote.status = "draft"

    await audit(db, "quote.updated", user_id=user.id, entity_type="quote", entity_id=quote.id)
    await db.commit()
    return await _build_public(quote, db)


@router.delete("/{quote_id}")
async def delete_quote(
    quote_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    verify_origin(request)
    quote = await get_owned_quote(db, user.id, quote_id)
    await db.delete(quote)
    await audit(db, "quote.deleted", user_id=user.id, entity_type="quote", entity_id=quote_id)
    await db.commit()
    return {"message": "Quote deleted."}


def _issue_public_token(quote: Quote, ttl_days: int = DEFAULT_TOKEN_TTL_DAYS) -> str:
    """Generate + store a public token hash for a quote. Returns the raw token once."""
    raw = generate_public_quote_token()
    quote.public_token_hash = hash_token(raw)
    quote.public_token_expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
    return raw


@router.post("/{quote_id}/send", response_model=QuoteResponse)
async def send_quote(
    quote_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    verify_origin(request)
    quote = await get_owned_quote(db, user.id, quote_id)
    raw = _issue_public_token(quote)
    quote.status = "sent" if quote.status in ("draft", "viewed") else quote.status
    await audit(db, "quote.sent", user_id=user.id, entity_type="quote", entity_id=quote.id)
    await db.commit()
    web = await _build_public(quote, db)
    public_link = f"{settings.frontend_url}/q/{raw}" if raw else None
    return QuoteResponse(quote=web, public_link=public_link)


@router.get("/{quote_id}/download-docx")
async def download_quote_docx(
    quote_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the quote as a filled DOCX file.

    Uses the business's custom DOCX template when one is active and readable;
    otherwise falls back to the built-in QuoteFlow DOCX layout. Custom quotation
    templates remain DOCX-only — PDF is generated by converting this document.
    """
    quote = await get_owned_quote(db, user.id, quote_id)
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    ).scalar_one_or_none()
    customer = await db.get(Customer, quote.customer_id) if quote.customer_id else None
    tax_rate_percent = str(((profile.tax_rate_bps if profile else 0) or 0) / 100)

    filled = fill_custom_docx(profile, quote, customer, tax_rate_percent)
    if filled is None:
        filled = fill_docx_template(
            build_sample_docx(),
            quote_docx_values(profile, quote, customer, tax_rate_percent),
            items=quote_items(quote),
        )

    safe_filename = f"quotation-{quote.quote_number}.docx"
    return Response(
        content=filled,
        media_type=DOCX_MIME_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{quote_id}/generate-pdf")
async def generate_quote_pdf(
    quote_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await enforce(client_ip_key(request), "pdf_generate", limit=20, window_seconds=3600)
    quote = await get_owned_quote(db, user.id, quote_id)

    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    ).scalar_one_or_none()
    customer = await db.get(Customer, quote.customer_id) if quote.customer_id else None
    tax_rate_percent = str(((profile.tax_rate_bps if profile else 0) or 0) / 100)

    try:
        pdf_bytes, used_template = render_quote_pdf(
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

    await audit(db, "quote.pdf_generated", user_id=user.id, entity_type="quote", entity_id=quote.id)
    await db.commit()

    safe_filename = f"quotation-{quote.quote_number}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
            "X-QuoteFlow-Template": used_template,
        },
    )


@router.post("/{quote_id}/cancel", response_model=QuotePublic)
async def cancel_quote(
    quote_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotePublic:
    verify_origin(request)
    quote = await get_owned_quote(db, user.id, quote_id)
    if quote.status == "cancelled":
        raise bad_request("Quote is already cancelled.")
    quote.status = "cancelled"
    quote.public_token_hash = None
    quote.public_token_expires_at = None
    await audit(db, "quote.cancelled", user_id=user.id, entity_type="quote", entity_id=quote.id)
    await db.commit()
    return await _build_public(quote, db)


@router.post("/{quote_id}/revoke-link", response_model=QuotePublic)
async def revoke_link(
    quote_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotePublic:
    verify_origin(request)
    quote = await get_owned_quote(db, user.id, quote_id)
    quote.public_token_hash = None
    quote.public_token_expires_at = None
    await audit(db, "quote.link_revoked", user_id=user.id, entity_type="quote", entity_id=quote_id)
    await db.commit()
    return await _build_public(quote, db)


@router.post("/{quote_id}/copy-link", response_model=QuoteResponse)
async def copy_link(
    quote_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    """Re-issue a fresh public link (the previous one is revoked and the raw
    token is never stored). Returns the new link once."""
    verify_origin(request)
    quote = await get_owned_quote(db, user.id, quote_id)
    raw = _issue_public_token(quote)
    quote.status = "sent" if quote.status in ("draft", "viewed") else quote.status
    await audit(db, "quote.link_recopied", user_id=user.id, entity_type="quote", entity_id=quote_id)
    await db.commit()
    web = await _build_public(quote, db)
    return QuoteResponse(quote=web, public_link=f"{settings.frontend_url}/q/{raw}")
