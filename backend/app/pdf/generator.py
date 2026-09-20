"""Server-side PDF generation with ReportLab.

PDFs are generated on request in memory — never persisted to executable paths,
never leaked via filesystem paths, and never containing secrets.

All monetary values are consumed as integer minor units (cents) — the same
convention the database and quote detail API use — and converted to display
dollars exactly once via ``_fmt``. Quantities are never scaled.
"""

from __future__ import annotations

import io
import logging
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as _pdf_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import (
    Image as RLImage,
)

logger = logging.getLogger("quoteflow")

# ── Colour palette ──────────────────────────────────────────────────────
_PRIMARY = colors.HexColor("#1e40af")
_PRIMARY_LIGHT = colors.HexColor("#dbeafe")
_TEXT = colors.HexColor("#1e293b")
_TEXT_MUTED = colors.HexColor("#64748b")
_GRID = colors.HexColor("#e2e8f0")
_ROW_ALT = colors.HexColor("#f8fafc")

CURRENCY_SYMBOLS = {"USD": "$", "CAD": "CA$", "GBP": "\u00a3", "AUD": "A$"}

_STATUS_LABELS = {
    "draft": "DRAFT",
    "sent": "SENT",
    "paid": "PAID",
    "viewed": "VIEWED",
    "accepted": "ACCEPTED",
    "rejected": "REJECTED",
    "expired": "EXPIRED",
    "cancelled": "CANCELLED",
}

_STATUS_COLORS = {
    "draft": colors.HexColor("#64748b"),
    "sent": colors.HexColor("#2563eb"),
    "paid": colors.HexColor("#16a34a"),
    "viewed": colors.HexColor("#b45309"),
    "accepted": colors.HexColor("#16a34a"),
    "rejected": colors.HexColor("#dc2626"),
    "expired": colors.HexColor("#9ca3af"),
    "cancelled": colors.HexColor("#dc2626"),
}


# ── Canvas helpers ──────────────────────────────────────────────────────
class NoCompressionCanvas(_pdf_canvas.Canvas):
    """Uncompressed streams so text stays searchable / selectable."""

    def __init__(self, *args, **kwargs):
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)


def _draw_footer(canvas, doc):
    """Page number centred at the bottom of every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_TEXT_MUTED)
    canvas.drawCentredString(doc.pagesize[0] / 2, 0.35 * inch, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


# ── Formatting helpers ─────────────────────────────────────────────────
def _fmt(minor: int) -> str:
    """Minor units (cents) → formatted dollar string, e.g. 45000 → '450.00'."""
    return f"{Decimal(minor) / 100:,.2f}"


def _sym(currency: str) -> str:
    """Currency symbol prefix, falling back to the ISO code for currencies whose
    symbol isn't renderable with the standard WinAnsi fonts (e.g. INR ₹)."""
    sym = CURRENCY_SYMBOLS.get(currency)
    return sym if sym is not None else f"{currency.upper()} "


def _esc(text: str) -> str:
    """Escape XML-sensitive characters for ReportLab paragraphs."""
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _lines(text: str) -> list[str]:
    """Non-empty, stripped lines from a multi-line block."""
    return [line.strip() for line in str(text or "").split("\n") if line.strip()]


# ── Main generator ─────────────────────────────────────────────────────
def generate_quote_pdf(
    *,
    # ── Business ──
    business_name: str = "",
    owner_name: str = "",
    business_email: str = "",
    business_phone: str = "",
    business_address: str = "",
    business_gstin: str = "",
    logo_bytes: bytes | None = None,
    # ── Quote metadata ──
    quote_number: str = "",
    status: str = "draft",
    issue_date: str = "",
    expiry_date: str = "",
    accepted_date: str = "",
    currency: str = "USD",
    payment_terms: str = "",
    due_date: str = "",
    # ── Customer ("BILL TO") ──
    customer_name: str = "",
    customer_company: str = "",
    customer_email: str = "",
    customer_phone: str = "",
    customer_address: str = "",
    # ── Line items (minor units, exactly as stored) ──
    items: list[dict] | None = None,
    # ── Totals (minor units — same convention as DB) ──
    subtotal_minor: int = 0,
    discount_minor: int = 0,
    tax_minor: int = 0,
    total_minor: int = 0,
    tax_rate_percent: str = "0",
    # ── Footer sections ──
    notes: str = "",
    terms: str = "",
    payment_instructions: str = "",
) -> bytes:
    """Build a polished, A4, multi-page quotation PDF entirely in memory.
    This is the built-in default QuoteFlow template."""
    buf = io.BytesIO()
    page_w, page_h = A4
    margin = 0.6 * inch
    content_w = page_w - 2 * margin
    top_margin = 0.55 * inch

    # ── Document ──
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=top_margin,
        bottomMargin=0.6 * inch,
        title=f"Quote {quote_number} — {business_name}",
    )
    frame = Frame(margin, margin, content_w, page_h - top_margin - 0.6 * inch, id="main")
    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=_draw_footer)])

    # ── Styles ──
    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("QTitle", parent=styles["Normal"], fontSize=24, fontName="Helvetica-Bold", textColor=_PRIMARY, alignment=TA_RIGHT, spaceAfter=6)
    s_badge = ParagraphStyle("QBadge", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)
    s_biz = ParagraphStyle("BizName", parent=styles["Normal"], fontSize=16, fontName="Helvetica-Bold", textColor=_TEXT, spaceAfter=3)
    s_detail = ParagraphStyle("Detail", parent=styles["Normal"], fontSize=8.5, textColor=_TEXT_MUTED, leading=12)
    s_section = ParagraphStyle("Section", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", textColor=_PRIMARY, spaceBefore=12, spaceAfter=5)
    s_label = ParagraphStyle("Label", parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold", textColor=_TEXT_MUTED, spaceAfter=1)
    s_body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=13, textColor=_TEXT)
    s_small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, leading=11, textColor=_TEXT_MUTED)
    s_cell = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=_TEXT)
    s_cell_r = ParagraphStyle("CellR", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=_TEXT, alignment=TA_RIGHT)
    s_cell_b = ParagraphStyle("CellB", parent=styles["Normal"], fontSize=9, leading=11, textColor=_TEXT, fontName="Helvetica-Bold")
    s_cell_rb = ParagraphStyle("CellRB", parent=styles["Normal"], fontSize=9, leading=11, textColor=_PRIMARY, fontName="Helvetica-Bold", alignment=TA_RIGHT)
    s_hdr = ParagraphStyle("Hdr", parent=styles["Normal"], fontSize=8.5, fontName="Helvetica-Bold", textColor=colors.white, leading=11)
    s_hdr_r = ParagraphStyle("HdrR", parent=styles["Normal"], fontSize=8.5, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT, leading=11)
    s_meta_l = ParagraphStyle("MetaL", parent=styles["Normal"], fontSize=8, textColor=_TEXT_MUTED, leading=10)
    s_meta_r = ParagraphStyle("MetaR", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=_TEXT, alignment=TA_RIGHT, leading=11)
    s_cname = ParagraphStyle("CustName", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", textColor=_TEXT, spaceAfter=1)
    s_ccompany = ParagraphStyle("CustCo", parent=styles["Normal"], fontSize=9, textColor=_TEXT_MUTED, spaceAfter=1)
    s_legal = ParagraphStyle("Legal", parent=s_small, alignment=TA_CENTER)

    sym = _sym(currency)
    status_label = _STATUS_LABELS.get(status, status.upper())
    story: list = []

    # ── HEADER ──────────────────────────────────────────────────────────
    # Left: logo (if any) + business identity
    left: list = []
    if logo_bytes:
        try:
            reader = ImageReader(io.BytesIO(logo_bytes))
            iw, ih = reader.getSize()
            scale = min(1.6 * inch / iw, 0.9 * inch / ih, 1.0)
            left.append(RLImage(io.BytesIO(logo_bytes), width=iw * scale, height=ih * scale))
            left.append(Spacer(1, 6))
        except Exception:
            pass  # never crash on a bad logo

    left.append(Paragraph(_esc(business_name) or "Business", s_biz))
    if owner_name:
        left.append(Paragraph(_esc(owner_name), s_detail))
    if business_email:
        left.append(Paragraph(_esc(business_email), s_detail))
    if business_phone:
        left.append(Paragraph(_esc(business_phone), s_detail))
    for line in _lines(business_address):
        left.append(Paragraph(_esc(line), s_detail))
    if business_gstin:
        left.append(Paragraph(f"GSTIN: {_esc(business_gstin)}", s_detail))

    # Right: QUOTATION title, status badge, quote meta
    right: list = [Paragraph("QUOTATION", s_title)]
    badge = Table([[Paragraph(status_label, s_badge)]], colWidths=[1.4 * inch], rowHeights=[0.28 * inch])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _STATUS_COLORS.get(status, _PRIMARY)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    badge.hAlign = "RIGHT"
    right.append(badge)
    right.append(Spacer(1, 8))

    meta_rows = []
    for label, val in [("Quote #", quote_number), ("Issue date", issue_date)]:
        if val:
            meta_rows.append([Paragraph(label, s_meta_l), Paragraph(_esc(str(val)), s_meta_r)])
    if meta_rows:
        mt = Table(meta_rows, colWidths=[0.9 * inch, 1.9 * inch])
        mt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        right.append(mt)

    header = Table([[left, right]], colWidths=[content_w * 0.55, content_w * 0.45])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(header)

    # Divider bar
    story.append(Spacer(1, 8))
    divider = Table([[""]], colWidths=[content_w], rowHeights=[2])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), _PRIMARY), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(divider)
    story.append(Spacer(1, 12))

    # ── BILL TO ─────────────────────────────────────────────────────────
    story.append(Paragraph("BILL TO", s_section))
    if customer_name:
        story.append(Paragraph(_esc(customer_name), s_cname))
    if customer_company:
        story.append(Paragraph(_esc(customer_company), s_ccompany))
    if customer_email:
        story.append(Paragraph(_esc(customer_email), s_body))
    if customer_phone:
        story.append(Paragraph(customer_phone, s_body))
    for line in _lines(customer_address):
        story.append(Paragraph(_esc(line), s_body))
    if not any([customer_name, customer_company, customer_email, customer_phone, customer_address]):
        story.append(Paragraph("(No customer information provided)", s_small))
    story.append(Spacer(1, 8))

    # ── QUOTE DETAILS STRIP ─────────────────────────────────────────────
    details = []
    if currency:
        details.append(("Currency", currency))
    if accepted_date:
        details.append(("Status", "Accepted"))
        details.append(("Accepted on", accepted_date))
    if payment_terms:
        details.append(("Payment terms", payment_terms))
    if due_date:
        details.append(("Due date", due_date))
    if expiry_date:
        details.append(("Valid until", expiry_date))
    if details:
        col_w = content_w / len(details)
        cells = []
        for label, value in details:
            cells.append([
                Paragraph(label, s_label),
                Paragraph(_esc(str(value)), s_body),
            ])
        dtbl = Table([cells], colWidths=[col_w] * len(details))
        dtbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _ROW_ALT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.5, _GRID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, _GRID),
        ]))
        story.append(dtbl)
        story.append(Spacer(1, 10))

    # ── LINE ITEMS TABLE ────────────────────────────────────────────────
    story.append(Paragraph("Line Items", s_section))

    safe_items = items or []
    has_item_discount = any(int(it.get("discount_minor", 0) or 0) > 0 for it in safe_items)
    has_item_tax = any(int(it.get("tax_minor", 0) or 0) > 0 for it in safe_items)

    num_w = 0.28 * inch
    qty_w = 0.45 * inch
    unit_w = 0.55 * inch
    price_w = 0.90 * inch
    den_w = 0.75 * inch
    tax_w = 0.70 * inch
    amount_w = 0.95 * inch

    fixed_w = num_w + qty_w + unit_w + price_w + amount_w
    if has_item_discount:
        fixed_w += den_w
    if has_item_tax:
        fixed_w += tax_w
    desc_w = content_w - fixed_w

    headers = [Paragraph("#", s_hdr), Paragraph("Description", s_hdr)]
    widths = [num_w, desc_w, qty_w, unit_w, price_w]
    headers.append(Paragraph("Qty", s_hdr_r))
    headers.append(Paragraph("Unit", s_hdr))
    headers.append(Paragraph("Unit Price", s_hdr_r))
    if has_item_discount:
        headers.append(Paragraph("Discount", s_hdr_r))
        widths.append(den_w)
    if has_item_tax:
        headers.append(Paragraph("Tax", s_hdr_r))
        widths.append(tax_w)
    headers.append(Paragraph("Amount", s_hdr_r))
    widths.append(amount_w)

    rows = [headers]
    for idx, it in enumerate(safe_items, start=1):
        row = [
            Paragraph(str(idx), s_cell),
            Paragraph(_esc(str(it.get("description", ""))), s_cell),
            Paragraph(_esc(str(it.get("quantity", "0"))), s_cell_r),
            Paragraph(_esc(str(it.get("unit", ""))), s_cell),
            Paragraph(f"{sym}{_fmt(int(it.get('unit_price_minor', 0)))}", s_cell_r),
        ]
        if has_item_discount:
            row.append(Paragraph(f"-{sym}{_fmt(int(it.get('discount_minor', 0) or 0))}", s_cell_r))
        if has_item_tax:
            row.append(Paragraph(f"{sym}{_fmt(int(it.get('tax_minor', 0) or 0))}", s_cell_r))
        row.append(Paragraph(f"{sym}{_fmt(int(it.get('line_total_minor', 0)))}", s_cell_r))
        rows.append(row)

    itbl = Table(rows, colWidths=widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.4, _GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(2, len(rows), 2):
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), _ROW_ALT))
    itbl.setStyle(TableStyle(style_cmds))
    story.append(itbl)
    story.append(Spacer(1, 12))

    # ── TOTALS ──────────────────────────────────────────────────────────
    trows = []
    trows.append([Paragraph("Subtotal", s_cell), Paragraph(f"{sym}{_fmt(subtotal_minor)}", s_cell_r)])
    if discount_minor > 0:
        trows.append([Paragraph("Discount", s_cell), Paragraph(f"-{sym}{_fmt(discount_minor)}", s_cell_r)])
        trows.append([Paragraph("Taxable Amount", s_cell), Paragraph(f"{sym}{_fmt(subtotal_minor - discount_minor)}", s_cell_r)])
    if tax_minor > 0:
        trows.append([Paragraph(f"Tax ({_esc(tax_rate_percent)}%)", s_cell), Paragraph(f"{sym}{_fmt(tax_minor)}", s_cell_r)])
    trows.append([Paragraph("TOTAL", s_cell_b), Paragraph(f"{sym}{_fmt(total_minor)}", s_cell_rb)])

    ttbl = Table(trows, colWidths=[2.6 * inch, 1.5 * inch], hAlign="RIGHT")
    tstyle = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, -1), (-1, -1), _PRIMARY_LIGHT),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, _PRIMARY),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
    ]
    if len(trows) > 1:
        tstyle.append(("LINEBELOW", (0, -2), (-1, -2), 0.25, _GRID))
    ttbl.setStyle(TableStyle(tstyle))
    story.append(ttbl)

    # ── FOOTER SECTIONS ─────────────────────────────────────────────────
    if notes:
        story.append(Paragraph("Notes", s_section))
        story.append(Paragraph(_esc(notes), s_body))
    if terms:
        story.append(Paragraph("Terms & Conditions", s_section))
        story.append(Paragraph(_esc(terms), s_body))
    if payment_instructions:
        story.append(Paragraph("Payment Information", s_section))
        story.append(Paragraph(_esc(payment_instructions), s_body))

    # Signature area
    story.append(Spacer(1, 22))
    sig = Table([
        [Paragraph("Authorized by", s_label), Paragraph("Signature", s_label)],
        [Paragraph(_esc(owner_name) if owner_name else "&nbsp;", s_cell_b), Paragraph("&nbsp;", s_cell)],
        [Paragraph("", s_cell), Paragraph("_" * 44, s_cell)],
    ], colWidths=[content_w * 0.5, content_w * 0.5])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story.append(sig)

    story.append(Spacer(1, 18))
    story.append(Paragraph("Thank you for your business!", ParagraphStyle("ThankYou", parent=s_body, fontName="Helvetica-Bold", fontSize=10.5, textColor=_PRIMARY, alignment=TA_CENTER)))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "This is a quotation only and is not a legally binding contract. "
        "The business owner is responsible for legal compliance in their jurisdiction.",
        s_legal,
    ))

    # ── Build ──
    doc.build(story, canvasmaker=NoCompressionCanvas)
    return buf.getvalue()
