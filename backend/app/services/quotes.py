"""Quote service helpers: numbering, item application, serialization, ownership."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.models.quote import Quote, QuoteItem
from app.schemas.quote import QuoteItemIn, QuotePublic
from app.services.quote_calc import calculate_quote, format_percent


async def next_quote_number(db: AsyncSession, user_id: int) -> str:
    """Generate the next quote number for a business (sequential per user)."""
    result = await db.execute(
        select(func.count(Quote.id)).where(Quote.user_id == user_id)
    )
    count = result.scalar_one() or 0
    year = datetime.now(UTC).year
    return f"Q-{year}-{count + 1:04d}"


def item_payload(items: list[QuoteItemIn] | list[dict]) -> list[dict]:
    """Normalize quote item input into calculation payloads."""
    payload = []
    for idx, item in enumerate(items):
        if isinstance(item, QuoteItemIn):
            payload.append(
                {
                    "description": item.description,
                    "quantity": str(item.quantity),
                    "unit": item.unit,
                    "unit_price_minor": item.unit_price_minor,
                    "sort_order": item.sort_order or idx,
                }
            )
        else:
            payload.append(item)
    return payload


async def apply_items_to_quote(db: AsyncSession, quote: Quote, items: list[QuoteItemIn]) -> None:
    """Rewrite a quote's items and recalculate line totals. Caller commits."""
    payload = item_payload(items)
    # Load the collection first — touching `quote.items` before it is loaded
    # triggers an implicit lazy load, which raises MissingGreenlet in async.
    await db.refresh(quote, attribute_names=["items"])
    quote.items.clear()
    await db.flush()
    for _idx, raw in enumerate(payload):
        line_result = calculate_quote(
            [raw], discount_minor=0, tax_rate_bps=0
        ).lines[0]
        quote.items.append(
            QuoteItem(
                description=line_result.description,
                quantity=line_result.quantity,
                unit=line_result.unit,
                unit_price_minor=line_result.unit_price_minor,
                line_total_minor=line_result.line_total_minor,
                sort_order=line_result.sort_order,
            )
        )
    await db.flush()


async def get_owned_quote(db: AsyncSession, user_id: int, quote_id: int, *, raise_missing: bool = True) -> Quote | None:
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.user_id == user_id))
    quote = result.scalar_one_or_none()
    if quote is None and raise_missing:
        raise not_found("Quote not found.")
    return quote


def serialize_quote(
    quote: Quote,
    tax_rate_bps: int,
    customer_name: str = "",
    include_items: bool = True,
    public_link_token: str = "",
) -> QuotePublic:
    data = {
        "id": quote.id,
        "quote_number": quote.quote_number,
        "customer_id": quote.customer_id,
        "status": quote.status,
        "issue_date": quote.issue_date,
        "expiry_date": quote.expiry_date,
        "currency": quote.currency,
        "subtotal_minor": quote.subtotal_minor,
        "discount_minor": quote.discount_minor,
        "tax_minor": quote.tax_minor,
        "total_minor": quote.total_minor,
        "notes": quote.notes,
        "terms": quote.terms,
        "created_at": quote.created_at,
        "updated_at": quote.updated_at,
        "items": quote.items,
        "customer_name": customer_name,
        "public_link_token": public_link_token,
    }
    data["breakdown"] = {
        "subtotal_minor": quote.subtotal_minor,
        "discount_minor": quote.discount_minor,
        "tax_minor": quote.tax_minor,
        "total_minor": quote.total_minor,
        "tax_rate_percent": str(quote_calc_tax_percent(tax_rate_bps)),
    }
    data["has_public_link"] = quote.public_token_hash is not None
    return QuotePublic.model_validate(data)


def quote_calc_tax_percent(tax_rate_bps: int) -> str:
    return format_percent(tax_rate_bps)
