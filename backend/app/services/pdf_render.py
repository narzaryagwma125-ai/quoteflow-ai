"""Shared quote → PDF rendering.

Used by both the authenticated quote endpoints and the public (customer-facing)
accepted-quote PDF so the output is identical on the dashboard and on the
public acceptance page. The business's custom DOCX quotation template is used
when configured and readable (converted to PDF via LibreOffice); otherwise the
built-in default ReportLab template is used.

Money convention everywhere: integer minor units (cents), exactly as stored.
"""

from __future__ import annotations

import logging

from app.pdf.generator import generate_quote_pdf as build_pdf
from app.services import docx_to_pdf
from app.services.docx_templates import fill_docx_template, format_currency, format_date
from app.services.logo import logo_bytes_for_docx
from app.services.templates import load_custom_docx
from app.uploads.store import read_logo

logger = logging.getLogger("quoteflow")


def address_lines(profile) -> list[str]:
    """Multi-line postal address of a business profile, filled lines only."""
    if not profile:
        return []
    lines = []
    if profile.address_line_1:
        lines.append(profile.address_line_1)
    if profile.address_line_2:
        lines.append(profile.address_line_2)
    city_state = ", ".join(x for x in [profile.city, profile.state_or_province, profile.postal_code] if x)
    if city_state:
        lines.append(city_state)
    if profile.country:
        lines.append(profile.country)
    return lines


def quote_items(quote) -> list[dict]:
    """Flat line-item payload shared by PDF and DOCX rendering."""
    return [
        {
            "description": item.description,
            "quantity": item.quantity,
            "unit": item.unit,
            "unit_price_minor": item.unit_price_minor,
            "line_total_minor": item.line_total_minor,
        }
        for item in quote.items
    ]


def quote_docx_values(profile, quote, customer, tax_rate_percent: str) -> dict[str, str]:
    """Placeholder values used to fill a custom DOCX quotation template."""
    docx_currency = quote.currency or "USD"
    return {
        "business_name": profile.business_name if profile else "Business",
        "business_owner": profile.owner_name if profile else "",
        "business_email": profile.email if profile else "",
        "business_phone": profile.phone if profile else "",
        "business_address": "\n".join(address_lines(profile)),
        "business_tax_id": "",
        "business_currency": docx_currency,
        "quote_number": quote.quote_number,
        "issue_date": format_date(quote.issue_date.isoformat()),
        "valid_until": format_date(quote.expiry_date.isoformat()) if quote.expiry_date else "",
        "status": quote.status.upper(),
        "accepted_date": format_date(quote.responded_at.date().isoformat()) if quote.responded_at else "",
        "currency": docx_currency,
        "customer_name": customer.name if customer else "",
        "customer_company": "",
        "customer_email": customer.email if customer else "",
        "customer_phone": customer.phone if customer else "",
        "customer_address": customer.address if customer else "",
        "subtotal": format_currency(quote.subtotal_minor, docx_currency),
        "discount": format_currency(quote.discount_minor, docx_currency),
        "tax_rate": f"{tax_rate_percent}%",
        "tax_amount": format_currency(quote.tax_minor, docx_currency),
        "total": format_currency(quote.total_minor, docx_currency),
        "notes": quote.notes or "",
        "payment_terms": quote.terms or "",
        "signature": profile.owner_name if profile else "",
    }


def fill_custom_docx(profile, quote, customer, tax_rate_percent: str) -> bytes | None:
    """Fill the active custom DOCX template with live quote data.

    Returns ``None`` when no custom DOCX template is configured/readable so the
    caller can fall back to the built-in template. The logo is embedded into the
    DOCX header (respecting position/size/the show-logo toggle) the same way the
    PDF generator does.
    """
    if not (profile and profile.template_type == "custom_docx" and profile.custom_docx_file_id):
        return None

    try:
        docx_bytes = load_custom_docx(profile)
    except Exception:
        logger.exception("Custom DOCX load failed for user %s; falling back.", profile.user_id)
        return None
    if docx_bytes is None:
        return None

    show_logo = profile.show_logo_on_quotation if profile else True
    logo_raw = None
    logo_content_type = ""
    if profile and profile.logo_file_id and show_logo:
        logo = profile.logo_file
        if logo is not None and logo.stored_name:
            logo_raw = read_logo(logo.stored_name)
            logo_content_type = logo.content_type

    docx_logo = (
        logo_bytes_for_docx(logo_raw, logo_content_type)
        if logo_raw is not None
        else None
    )
    return fill_docx_template(
        docx_bytes,
        quote_docx_values(profile, quote, customer, tax_rate_percent),
        items=quote_items(quote),
        logo_bytes=docx_logo,
        logo_position=profile.logo_position if profile else "left",
        logo_size=profile.logo_size if profile else "medium",
        show_logo=True,  # the toggle was already honored above
    )


def render_quote_pdf(
    *,
    profile,
    quote,
    customer,
    tax_rate_percent: str,
) -> tuple[bytes, str]:
    """Render a quote to PDF bytes using the exact stored quote data.

    Returns ``(pdf_bytes, used_template)`` where ``used_template`` is
    ``"custom_docx"`` or ``"default"``.

    Raises ``docx_to_pdf.DocxConversionUnavailable`` when a custom DOCX template
    is configured but LibreOffice (the DOCX→PDF converter) is not installed; the
    default template never depends on it.
    """
    logo_bytes = None
    logo_content_type = ""
    if profile and profile.logo_file_id:
        logo = profile.logo_file
        if logo is not None and logo.stored_name:
            logo_bytes = read_logo(logo.stored_name)
            logo_content_type = logo.content_type

    show_logo = profile.show_logo_on_quotation if profile else True
    effective_logo_bytes = logo_bytes if (show_logo and logo_bytes) else None

    items = quote_items(quote)
    accepted_date = quote.responded_at.date().isoformat() if quote.responded_at else ""

    def _build_default() -> bytes:
        return build_pdf(
            business_name=profile.business_name if profile else "Business",
            owner_name=profile.owner_name if profile else "",
            business_email=profile.email if profile else "",
            business_phone=profile.phone if profile else "",
            business_address="\n".join(address_lines(profile)),
            quote_number=quote.quote_number,
            status=quote.status,
            issue_date=quote.issue_date.isoformat(),
            expiry_date=quote.expiry_date.isoformat() if quote.expiry_date else "",
            accepted_date=accepted_date,
            currency=quote.currency,
            customer_name=customer.name if customer else "",
            customer_email=customer.email if customer else "",
            customer_phone=customer.phone if customer else "",
            customer_address=customer.address if customer else "",
            items=items,
            subtotal_minor=quote.subtotal_minor,
            discount_minor=quote.discount_minor,
            tax_minor=quote.tax_minor,
            total_minor=quote.total_minor,
            tax_rate_percent=tax_rate_percent,
            notes=quote.notes,
            terms=quote.terms,
            logo_bytes=(
                logo_bytes_for_docx(effective_logo_bytes, logo_content_type)
                if effective_logo_bytes
                else None
            ),
        )

    pdf_bytes = None
    used_template = "default"

    if profile and profile.template_type == "custom_docx" and profile.custom_docx_file_id:
        filled = fill_custom_docx(profile, quote, customer, tax_rate_percent)
        if filled is not None:
            if not docx_to_pdf.is_converter_available():
                # No converter installed — clear error, default template still works.
                raise docx_to_pdf.DocxConversionUnavailable()

            try:
                pdf_bytes = docx_to_pdf.convert_docx_to_pdf(filled)
                used_template = "custom_docx"
            except docx_to_pdf.DocxConversionUnavailable:
                raise
            except Exception:
                # Never expose a stack trace to the user; fall back to the default
                # professional template on any custom DOCX failure.
                logger.exception(
                    "Custom DOCX PDF generation failed for quote %s (user %s); using default.",
                    quote.id,
                    quote.user_id,
                )
                pdf_bytes = None

    if pdf_bytes is None:
        pdf_bytes = _build_default()

    return pdf_bytes, used_template
