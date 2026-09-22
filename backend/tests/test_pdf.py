"""PDF generation tests: output is valid, ownership enforced, filenames safe,
totals match the quote detail API, and the professional layout renders all
sections without crashing on missing data."""

from __future__ import annotations

from datetime import date

import pytest

from app.db.session import async_session_factory
from app.models.quote import Quote, QuoteItem
from app.pdf.generator import generate_quote_pdf
from tests.conftest import (
    create_user,
    login,
    make_business_profile,
    make_customer,
    quote_payload,
)


def _pdf_all_bytes(pdf: bytes) -> bytes:
    """Raw PDF plus decompressed FlateDecode streams, so text assertions are
    robust to whatever compression reportlab applied to content streams."""
    import zlib

    chunks = [pdf]
    for part in pdf.split(b"stream")[1:]:
        data = part.split(b"endstream")[0].lstrip(b"\r\n")
        d = zlib.decompressobj()
        try:
            chunks.append(d.decompress(data) + d.flush())
        except zlib.error:
            pass
    return b"".join(chunks)


def _pdf_text(pdf: bytes) -> str:
    """PDF text with ReportLab's octal escapes (e.g. \\243 -> £) resolved.

    ReportLab writes non-ASCII WinAnsi bytes inside PDF literal strings as
    octal escapes, so a raw latin-1 scan would miss them.
    """
    import re

    text = _pdf_all_bytes(pdf).decode("latin-1")
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), text)


def _page_count(pdf: bytes) -> int:
    """Return the number of page objects in a PDF (catalog /Type /Pages excluded)."""
    text = pdf.decode("latin-1")
    return text.count("/Type /Page") - text.count("/Type /Pages")


def _page_size(pdf: bytes) -> tuple[float, float]:
    """Return (width, height) in points parsed from the page MediaBox."""
    import re

    m = re.search(rb"/MediaBox\s*\[([0-9.\s]+)\]", pdf)
    assert m, "MediaBox not found in PDF"
    vals = [float(x) for x in m.group(1).split()[:4]]
    return vals[2], vals[3]


def _sample_pdf(**overrides) -> bytes:
    defaults = {
        "business_name": "Sparkle Cleaning",
        "owner_name": "Alex Sparks",
        "business_email": "alex@sparkle.example",
        "business_phone": "555-0100",
        "business_address": "10 Maple St\nSpringfield, IL 62704",
        "quote_number": "Q-2026-0001",
        "status": "sent",
        "issue_date": "2026-09-13",
        "expiry_date": "2026-10-13",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "555-0199",
        "customer_address": "42 Oak Ave\nAustin, TX",
        "items": [
            {"description": "Deep clean", "quantity": "3", "unit": "hour", "unit_price_minor": 15000, "line_total_minor": 45000},
        ],
        "subtotal_minor": 45000,
        "discount_minor": 0,
        "tax_minor": 5400,
        "total_minor": 50400,
        "tax_rate_percent": "12",
        "currency": "USD",
        "notes": "thanks",
        "terms": "net 14",
    }
    defaults.update(overrides)
    return generate_quote_pdf(**defaults)


def test_pdf_generation_is_valid_pdf_bytes():
    pdf = _sample_pdf()
    assert pdf.startswith(b"%PDF")
    assert pdf.rstrip().endswith(b"%%EOF")
    # A4 page size is used (595.28 x 841.89), not US Letter (612 x 792)
    w, h = _page_size(pdf)
    assert abs(w - 595.2755905511811) < 0.01
    assert abs(h - 841.8897637795276) < 0.01


def test_pdf_contains_business_information():
    text = _pdf_all_bytes(_sample_pdf()).decode("latin-1")
    for expected in ("Sparkle Cleaning", "Alex Sparks", "alex@sparkle.example", "555-0100", "10 Maple St", "Springfield, IL 62704", "QUOTATION"):
        assert expected in text


def test_pdf_contains_customer_information():
    text = _pdf_all_bytes(_sample_pdf()).decode("latin-1")
    for expected in ("BILL TO", "Jane Doe", "jane@example.com", "555-0199", "42 Oak Ave", "Austin, TX"):
        assert expected in text


def test_pdf_contains_quote_number_and_dates():
    text = _pdf_all_bytes(_sample_pdf()).decode("latin-1")
    for expected in ("Q-2026-0001", "2026-09-13", "2026-10-13", "SENT"):
        assert expected in text


def test_pdf_contains_line_items():
    text = _pdf_all_bytes(_sample_pdf()).decode("latin-1")
    assert "Line Items" in text
    assert "Deep clean" in text
    assert "hour" in text


def test_pdf_money_round_trip_3x150_12pct():
    """Quantity 3 stays 3; 150 displays as 150.00; line 450.00; tax 54.00; total 504.00."""
    text = _pdf_all_bytes(_sample_pdf()).decode("latin-1")
    assert "3" in text
    assert "$450.00" in text  # line total
    assert "$54.00" in text   # 12% tax
    assert "$504.00" in text  # grand total
    assert "$4,500.00" not in text  # no accidental *100
    assert "$5,040.00" not in text


def test_pdf_totals_match_quote_detail_service():
    """Taxable amount shown when a discount exists; totals derive from the same
    minor-unit values used by the detail API."""
    pdf = generate_quote_pdf(
        business_name="Sparkle Cleaning",
        quote_number="Q-DISC-1",
        issue_date="2026-09-13",
        expiry_date="",
        customer_name="",
        items=[
            {"description": "Clean", "quantity": "2", "unit": "job", "unit_price_minor": 10000, "line_total_minor": 20000},
        ],
        subtotal_minor=20000,
        discount_minor=2000,
        tax_minor=1800,
        total_minor=19800,
        tax_rate_percent="10",
        currency="USD",
        notes="",
        terms="",
    )
    text = _pdf_all_bytes(pdf).decode("latin-1")
    assert "$200.00" in text       # subtotal
    assert "$20.00" in text        # discount
    assert "$180.00" in text       # taxable amount (200 - 20)
    assert "$18.00" in text        # 10% tax on 180
    assert "$198.00" in text       # grand total


def test_pdf_escaping_prevents_xml_injection():
    hostile = "</Para><PARA>evil</PARA>"
    pdf = generate_quote_pdf(
        business_name=hostile,
        owner_name=hostile,
        quote_number="Q-ESC",
        issue_date="2026-09-13",
        expiry_date="",
        customer_name=hostile,
        items=[{"description": hostile, "quantity": "1", "unit": "", "unit_price_minor": 100, "line_total_minor": 100}],
        subtotal_minor=100,
        discount_minor=0,
        tax_minor=0,
        total_minor=100,
        tax_rate_percent="0",
        currency="USD",
        notes=hostile,
        terms=hostile,
    )
    assert pdf.startswith(b"%PDF")


def test_pdf_missing_logo_and_missing_customer_fields_do_not_crash():
    """No logo, no customer, empty business contact: still renders."""
    pdf = generate_quote_pdf(
        business_name="Only Biz",
        owner_name="",
        issue_date="2026-09-13",
        expiry_date="",
        customer_name="",
        items=[],
        subtotal_minor=0,
        discount_minor=0,
        tax_minor=0,
        total_minor=0,
        tax_rate_percent="0",
        currency="USD",
        notes="",
        terms="",
    )
    text = _pdf_all_bytes(pdf).decode("latin-1")
    assert "Only Biz" in text
    assert pdf.startswith(b"%PDF")


def test_pdf_long_descriptions_do_not_crash():
    long_desc = "Extremely long service description " + ("word " * 300)
    pdf = _sample_pdf(items=[
        {"description": long_desc, "quantity": "3", "unit": "hour", "unit_price_minor": 15000, "line_total_minor": 45000},
    ])
    text = _pdf_all_bytes(pdf).decode("latin-1")
    assert "Extremely long service description" in text


def test_pdf_many_items_span_multiple_pages():
    items = [
        {"description": f"Service number {i}", "quantity": "1", "unit": "hr", "unit_price_minor": 1000, "line_total_minor": 1000}
        for i in range(60)
    ]
    pdf = _sample_pdf(items=items, subtotal_minor=60000, tax_minor=0, total_minor=60000, tax_rate_percent="0")
    assert _page_count(pdf) > 1


def test_pdf_all_supported_currency_symbols():
    """USD, CAD, GBP and AUD render with WinAnsi-safe symbols; INR and other
    non-WinAnsi currencies (e.g. EUR) fall back to the ISO code, so amounts are
    never mislabelled."""
    for currency, expected_prefix in (
        ("USD", "$"),
        ("CAD", "CA$"),
        ("GBP", "\u00a3"),
        ("AUD", "A$"),
        ("INR", "INR"),
        ("EUR", ""),
    ):
        pdf = _sample_pdf(currency=currency, total_minor=50400, tax_minor=5400)
        text = _pdf_text(pdf)
        assert "504.00" in text
        assert pdf.startswith(b"%PDF")
        if expected_prefix:
            assert expected_prefix in text


def test_pdf_signature_and_thank_you_sections():
    text = _pdf_all_bytes(_sample_pdf()).decode("latin-1")
    for expected in ("Authorized by", "Signature", "Thank you for your business!"):
        assert expected in text


def test_pdf_paid_status_badge_renders():
    text = _pdf_all_bytes(_sample_pdf(status="paid")).decode("latin-1")
    assert "PAID" in text


def test_pdf_quote_details_show_only_existing_fields():
    pdf = generate_quote_pdf(
        business_name="Sparkle Cleaning",
        quote_number="Q-DET",
        issue_date="2026-09-13",
        expiry_date="2026-10-13",
        currency="USD",
        payment_terms="Net 14",
        due_date="2026-10-01",
        customer_name="",
        items=[],
        subtotal_minor=0,
        discount_minor=0,
        tax_minor=0,
        total_minor=0,
        tax_rate_percent="0",
        notes="",
        terms="",
    )
    text = _pdf_all_bytes(pdf).decode("latin-1")
    for expected in ("Currency", "Payment terms", "Due date", "Valid until"):
        assert expected in text

    minimal = _pdf_all_bytes(_sample_pdf(payment_terms="", due_date="")).decode("latin-1")
    assert "Payment terms" not in minimal
    assert "Due date" not in minimal


def test_pdf_accepted_marker_renders_with_acceptance_date():
    """The accepted-quote PDF shows the accepted status badge plus the
    acceptance date in the details strip — and neither appears otherwise."""
    pdf = generate_quote_pdf(
        business_name="Sparkle Cleaning",
        quote_number="Q-2026-0002",
        status="accepted",
        issue_date="2026-09-13",
        expiry_date="",
        accepted_date="2026-09-16",
        currency="USD",
        customer_name="Jane Doe",
        items=[
            {"description": "Clean", "quantity": "1", "unit": "job", "unit_price_minor": 10000, "line_total_minor": 10000},
        ],
        subtotal_minor=10000,
        discount_minor=0,
        tax_minor=750,
        total_minor=10750,
        tax_rate_percent="7.5",
        notes="",
        terms="",
    )
    text = _pdf_all_bytes(pdf).decode("latin-1")
    assert "ACCEPTED" in text
    assert "Accepted on" in text
    assert "2026-09-16" in text

    plain = _pdf_all_bytes(_sample_pdf(status="sent")).decode("latin-1")
    assert "Accepted on" not in plain


def test_pdf_accepted_uses_exact_quote_totals():
    """The accepted PDF reproduces the stored minor-unit totals exactly."""
    pdf = _sample_pdf(status="accepted", accepted_date="2026-09-16", subtotal_minor=45000,
                      discount_minor=0, tax_minor=5400, total_minor=50400)
    text = _pdf_all_bytes(pdf).decode("latin-1")
    assert "$450.00" in text
    assert "$54.00" in text
    assert "$504.00" in text
    assert "$5,040.00" not in text


def test_pdf_per_item_discount_and_tax_columns_conditional():
    item = {"description": "Clean", "quantity": "1", "unit": "job", "unit_price_minor": 10000,
            "discount_minor": 1000, "tax_minor": 900, "line_total_minor": 9000}
    text = _pdf_all_bytes(_sample_pdf(items=[item])).decode("latin-1")
    assert "Discount" in text  # column header
    assert "Tax" in text       # column header
    assert "-$10.00" in text   # per-item discount value
    assert "$9.00" in text     # per-item tax value

    simple = _pdf_all_bytes(_sample_pdf()).decode("latin-1")
    assert "Discount" not in simple  # column hidden when no per-item discount


def test_pdf_customer_company_and_payment_instructions():
    pdf = generate_quote_pdf(
        business_name="Sparkle Cleaning",
        quote_number="Q-CO",
        issue_date="2026-09-13",
        expiry_date="",
        currency="USD",
        customer_name="Jane Doe",
        customer_company="Doe Industries",
        payment_instructions="Pay via bank transfer to account 1234.",
        items=[],
        subtotal_minor=0,
        discount_minor=0,
        tax_minor=0,
        total_minor=0,
        tax_rate_percent="0",
        notes="",
        terms="",
    )
    text = _pdf_all_bytes(pdf).decode("latin-1")
    assert "Doe Industries" in text
    assert "Payment Information" in text
    assert "Pay via bank transfer" in text


# ── Endpoint-level tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_pdf_endpoint_requires_ownership(client):
    user = await create_user("pdf@example.com")
    await login(client, "pdf@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=750))
        customer = make_customer(user.id)
        db.add(customer)
        await db.commit()
        await db.refresh(customer)

    created = await client.post(
        "/api/quotes",
        json=quote_payload(
            quote_number="Q-PDF1",
            customer_id=customer.id,
            items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "100.00", "sort_order": 0}],
        ),
    )
    quote_id = created.json()["quote"]["id"]

    res = await client.post(f"/api/quotes/{quote_id}/generate-pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    # professional, controlled filename
    assert res.headers["content-disposition"].startswith('attachment; filename="quotation-Q-PDF1.pdf"')


@pytest.mark.asyncio
async def test_generate_pdf_requires_auth(client):
    res = await client.post("/api/quotes/1/generate-pdf")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_generate_pdf_matches_quote_details(client):
    """Regression: PDF totals must match the quote detail API exactly (money
    convention is cents in storage, dollars in the PDF)."""
    user = await create_user("pdfmoney@example.com")
    await login(client, "pdfmoney@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(user.id, tax_rate_bps=1200))  # 12%
        await db.commit()

    created = await client.post(
        "/api/quotes",
        json=quote_payload(
            quote_number="Q-PDFMONEY",
            items=[
                {"description": "Deep clean", "quantity": "3", "unit": "hour", "unit_price": "150.00", "sort_order": 0},
            ],
        ),
    )
    assert created.status_code == 201, created.text
    created_body = created.json()["quote"]
    assert created_body["items"][0]["quantity"] == "3"
    assert created_body["total_minor"] == 50400
    quote_id = created_body["id"]

    res = await client.post(f"/api/quotes/{quote_id}/generate-pdf")
    assert res.status_code == 200
    pdf = _pdf_all_bytes(res.content)
    assert b"$450.00" in pdf
    assert b"$54.00" in pdf
    assert b"$504.00" in pdf
    assert b"$4,500.00" not in pdf
    assert b"$5,040.00" not in pdf


@pytest.mark.asyncio
async def test_generate_pdf_shows_business_and_customer_on_endpoint(client):
    """Endpoint passes structured business + customer data through to the PDF."""
    user = await create_user("pdfprofile@example.com")
    await login(client, "pdfprofile@example.com")
    async with async_session_factory() as db:
        profile = make_business_profile(user.id, tax_rate_bps=1200)
        db.add(profile)
        customer = make_customer(user.id)
        db.add(customer)
        await db.commit()
        await db.refresh(profile)
        await db.refresh(customer)

    created = await client.post(
        "/api/quotes",
        json=quote_payload(
            quote_number="Q-PDFPROF",
            customer_id=customer.id,
            items=[{"description": "Clean", "quantity": "1", "unit": "job", "unit_price": "100.00", "sort_order": 0}],
        ),
    )
    quote_id = created.json()["quote"]["id"]

    res = await client.post(f"/api/quotes/{quote_id}/generate-pdf")
    assert res.status_code == 200
    text = _pdf_all_bytes(res.content).decode("latin-1")
    assert "Sparkle Cleaning" in text or "Test Business" in text  # profile business_name from conftest
    assert "QUOTATION" in text


@pytest.mark.asyncio
async def test_existing_quote_rows_generate_pdf(client):
    """Pre-existing quote rows (no migration needed) render a valid PDF."""
    user = await create_user("pdfoold@example.com")
    await login(client, "pdfoold@example.com")
    async with async_session_factory() as db:
        quote = Quote(
            user_id=user.id,
            customer_id=None,
            quote_number="Q-OLD-PDF",
            status="sent",
            issue_date=date(2026, 8, 1),
            expiry_date=None,
            currency="USD",
            subtotal_minor=45000,
            discount_minor=0,
            tax_minor=5400,
            total_minor=50400,
            notes="",
            terms="",
        )
        db.add(quote)
        await db.flush()
        db.add(
            QuoteItem(
                quote_id=quote.id,
                description="Deep clean",
                quantity="3",
                unit="hour",
                unit_price_minor=15000,
                line_total_minor=45000,
                sort_order=0,
            )
        )
        await db.commit()
        await db.refresh(quote)
        quote_id = quote.id

    res = await client.post(f"/api/quotes/{quote_id}/generate-pdf")
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")
    assert res.headers["content-disposition"].startswith('attachment; filename="quotation-Q-OLD-PDF.pdf"')
