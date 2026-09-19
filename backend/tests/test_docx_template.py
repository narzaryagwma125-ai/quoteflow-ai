"""Custom DOCX quotation template tests.

Covers the DOCX-only MVP surface: default fallback, DOCX upload validation
(including rejection of PDF/PNG/JPG/XLSX/etc., oversized and corrupted files),
placeholder replacement (body, tables, headers, footers), line-item tables,
conversion to PDF with mocked converter, broken-converter fallback, converter
unavailability errors, ownership isolation, deletion, sample download, and the
quote-calculation regression guard.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from docx import Document
from reportlab.lib.pagesizes import A4
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.business_profile import BusinessProfile, TemplateFile
from tests.conftest import (
    create_user,
    login,
    make_business_profile,
    quote_payload,
)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ── Helpers ────────────────────────────────────────────────────────────
def _make_docx(
    paragraphs: list[str] | None = None,
    table_cells: list[str] | None = None,
    header: str | None = None,
    footer: str | None = None,
) -> bytes:
    doc = Document()
    for p in paragraphs or []:
        doc.add_paragraph(p)
    if table_cells:
        table = doc.add_table(rows=1, cols=len(table_cells))
        for i, text in enumerate(table_cells):
            table.rows[0].cells[i].text = text
    if header is not None:
        doc.sections[0].header.paragraphs[0].text = header
    if footer is not None:
        doc.sections[0].footer.paragraphs[0].text = footer
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _valid_docx() -> bytes:
    return _make_docx(
        paragraphs=[
            "{{business_name}}",
            "Quote {{quote_number}} for {{customer_name}}",
            "{{line_items}}",
            "Total: {{total}}",
        ]
    )


def _png_bytes() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63fccf000000050001000137f4f30000000049454e44ae426082"
    )


def _jpeg_bytes() -> bytes:
    return bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffdb004300" + "00" * 64 + "ffd9")


def _pdf_bytes() -> bytes:
    import reportlab.pdfgen.canvas as rl_canvas

    out = io.BytesIO()
    c = rl_canvas.Canvas(out, pagesize=A4)
    c.drawString(50, 780, "MY LETTERHEAD")
    c.showPage()
    c.save()
    return out.getvalue()


def _minimal_pdf() -> bytes:
    import reportlab.pdfgen.canvas as rl_canvas

    out = io.BytesIO()
    c = rl_canvas.Canvas(out, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(50, 780, "FILLED DOCX RENDERED")
    c.showPage()
    c.save()
    return out.getvalue()


def _page_count(pdf: bytes) -> int:
    text = pdf.decode("latin-1")
    return text.count("/Type /Page") - text.count("/Type /Pages")


async def _profile(user_id: int, *, add_docx: bool = False, tax_rate_bps: int = 750):
    async with async_session_factory() as db:
        profile = make_business_profile(user_id, tax_rate_bps=tax_rate_bps)
        db.add(profile)
        await db.flush()
        if add_docx:
            from app.uploads.store import store_template

            docx_bytes = _make_docx(["{{business_name}}", "{{quote_number}}", "{{line_items}}"])
            stored = store_template(DOCX_MIME, docx_bytes)
            tf = TemplateFile(
                user_id=user_id,
                stored_name=stored.name,
                original_name="template.docx",
                content_type=DOCX_MIME,
                size_bytes=len(docx_bytes),
            )
            db.add(tf)
            await db.flush()
            profile.template_type = "custom_docx"
            profile.custom_docx_file_id = tf.id
            profile.custom_docx_filename = "template.docx"
            profile.custom_docx_mime_type = DOCX_MIME
            profile.custom_docx_size = tf.size_bytes
            profile.custom_docx_uploaded_at = datetime.now(UTC)
            profile.custom_docx_version = 1
        await db.commit()
        await db.refresh(profile)
        return profile


async def _upload(client, filename: str, data: bytes, mime: str):
    files = {"file": (filename, io.BytesIO(data), mime)}
    return await client.post("/api/business-profile/template", files=files)


async def _create_quote(client, **overrides):
    payload = quote_payload(**overrides)
    res = await client.post("/api/quotes", json=payload)
    assert res.status_code == 201, res.text
    return res.json()["quote"]


# ── GET / template settings ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_template_settings_require_auth(client):
    res = await client.get("/api/business-profile/template")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    res = await _upload(client, "x.docx", _valid_docx(), DOCX_MIME)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_default_template_settings_when_nothing_uploaded(client):
    user = await create_user("dcx-none@example.com")
    await login(client, "dcx-none@example.com")
    await _profile(user.id)

    res = await client.get("/api/business-profile/template")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template_type"] == "default"
    assert body["has_custom_template"] is False
    assert body["custom_docx_file_id"] is None
    assert body["custom_docx_version"] == 0


@pytest.mark.asyncio
async def test_template_settings_missing_profile_404(client):
    await create_user("dcx-noprofile@example.com")
    await login(client, "dcx-noprofile@example.com")
    res = await client.get("/api/business-profile/template")
    assert res.status_code == 404


# ── POST / upload validation ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_successful_docx_template_upload(client):
    user = await create_user("dcx-up@example.com")
    await login(client, "dcx-up@example.com")
    await _profile(user.id)

    res = await _upload(client, "my-quote.docx", _valid_docx(), DOCX_MIME)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template_type"] == "custom_docx"
    assert body["has_custom_template"] is True
    assert body["custom_docx_filename"] == "my-quote.docx"
    assert body["custom_docx_mime_type"] == DOCX_MIME
    assert body["custom_docx_size"] == len(_valid_docx())
    assert body["custom_docx_version"] == 1


@pytest.mark.asyncio
async def test_upload_replaces_previous_docx_and_increments_version(client):
    user = await create_user("dcx-repl@example.com")
    await login(client, "dcx-repl@example.com")
    await _profile(user.id)

    await _upload(client, "a.docx", _make_docx(["one"]), DOCX_MIME)
    v1 = (await client.get("/api/business-profile/template")).json()["custom_docx_version"]
    await _upload(client, "b.docx", _make_docx(["two"]), DOCX_MIME)
    v2 = (await client.get("/api/business-profile/template")).json()["custom_docx_version"]
    assert v2 == v1 + 1


@pytest.mark.asyncio
async def test_pdf_upload_rejected(client):
    user = await create_user("dcx-pdf@example.com")
    await login(client, "dcx-pdf@example.com")
    await _profile(user.id)

    res = await _upload(client, "letter.pdf", _pdf_bytes(), "application/pdf")
    assert res.status_code == 415


@pytest.mark.asyncio
async def test_png_upload_rejected(client):
    user = await create_user("dcx-png@example.com")
    await login(client, "dcx-png@example.com")
    await _profile(user.id)

    res = await _upload(client, "letter.png", _png_bytes(), "image/png")
    assert res.status_code == 415


@pytest.mark.asyncio
async def test_jpeg_upload_rejected(client):
    user = await create_user("dcx-jpg@example.com")
    await login(client, "dcx-jpg@example.com")
    await _profile(user.id)

    res = await _upload(client, "letter.jpg", _jpeg_bytes(), "image/jpeg")
    assert res.status_code == 415


@pytest.mark.asyncio
async def test_xlsx_zip_exe_uploads_rejected(client):
    user = await create_user("dcx-other@example.com")
    await login(client, "dcx-other@example.com")
    await _profile(user.id)

    for name, data, mime in [
        ("spreadsheet.xlsx", b"PK\x03\x04\x00" + b"x" * 200,
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("archive.zip", b"PK\x03\x04\x00" + b"x" * 200, "application/zip"),
        ("tool.exe", b"MZ\x90\x00" + b"x" * 200, "application/octet-stream"),
    ]:
        res = await _upload(client, name, data, mime)
        assert res.status_code == 415, name


@pytest.mark.asyncio
async def test_wrong_extension_with_docx_mime_rejected(client):
    user = await create_user("dcx-ext@example.com")
    await login(client, "dcx-ext@example.com")
    await _profile(user.id)

    res = await _upload(client, "notadocx.pdf", _valid_docx(), DOCX_MIME)
    assert res.status_code == 415


@pytest.mark.asyncio
async def test_file_larger_than_5mb_rejected(client):
    user = await create_user("dcx-big@example.com")
    await login(client, "dcx-big@example.com")
    await _profile(user.id)

    from app.uploads.store import MAX_TEMPLATE_SIZE_BYTES

    big = _valid_docx() + (b"\x00" * (MAX_TEMPLATE_SIZE_BYTES + 1))
    res = await _upload(client, "big.docx", big, DOCX_MIME)
    assert res.status_code == 413


@pytest.mark.asyncio
async def test_corrupted_docx_rejected(client):
    user = await create_user("dcx-corrupt@example.com")
    await login(client, "dcx-corrupt@example.com")
    await _profile(user.id)

    data = b"PK\x03\x04" + (b"\x00\x01\x02" * 100)
    res = await _upload(client, "broken.docx", data, DOCX_MIME)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_empty_file_rejected(client):
    user = await create_user("dcx-empty@example.com")
    await login(client, "dcx-empty@example.com")
    await _profile(user.id)

    res = await _upload(client, "empty.docx", b"", DOCX_MIME)
    assert res.status_code in (400, 413, 415, 422)


@pytest.mark.asyncio
async def test_filename_path_traversal_sanitized(client):
    user = await create_user("dcx-traversal@example.com")
    await login(client, "dcx-traversal@example.com")
    await _profile(user.id)

    res = await _upload(client, "../../../etc/passwd.docx", _valid_docx(), DOCX_MIME)
    assert res.status_code == 200, res.text
    name = res.json()["custom_docx_filename"]
    assert ".." not in name
    assert "/" not in name and "\\" not in name


# ── Placeholder replacement (unit-level) ───────────────────────────────
def _fill(docx_bytes: bytes, values: dict[str, str], items=None) -> bytes:
    from app.services.docx_templates import fill_docx_template

    return fill_docx_template(docx_bytes, values, items=items)


def test_placeholder_replacement_in_body():
    docx = _make_docx(["{{business_name}}", "{{quote_number}}"])
    filled = _fill(docx, {"business_name": "Sparkle Cleaning", "quote_number": "Q-1"})
    doc = Document(io.BytesIO(filled))
    assert doc.paragraphs[0].text == "Sparkle Cleaning"
    assert doc.paragraphs[1].text == "Q-1"


@pytest.mark.asyncio
async def test_placeholder_replacement_in_table_cells():
    docx = _make_docx(["Intro"], table_cells=["{{business_name}}", "{{total}}"])
    filled = _fill(docx, {"business_name": "Sparkle", "total": "$450.00"})
    doc = Document(io.BytesIO(filled))
    row = doc.tables[0].rows[0]
    assert row.cells[0].text == "Sparkle"
    assert row.cells[1].text == "$450.00"


def test_placeholder_replacement_in_header_and_footer():
    docx = _make_docx(["body"], header="{{business_name}} — {{quote_number}}", footer="Page {{status}}")
    filled = _fill(docx, {"business_name": "Sparkle", "quote_number": "Q-9", "status": "SENT"})
    doc = Document(io.BytesIO(filled))
    assert doc.sections[0].header.paragraphs[0].text == "Sparkle — Q-9"
    assert doc.sections[0].footer.paragraphs[0].text == "Page SENT"


def test_line_items_table_inserted_for_multiple_items():
    items = [
        {"description": "Deep clean", "quantity": "3", "unit": "hour", "unit_price_minor": 15000, "line_total_minor": 45000},
        {"description": "Window wash", "quantity": "2", "unit": "window", "unit_price_minor": 2500, "line_total_minor": 5000},
    ]
    docx = _make_docx(["{{business_name}}", "{{line_items}}"])
    filled = _fill(docx, {"business_name": "Sparkle"}, items=items)
    doc = Document(io.BytesIO(filled))

    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert len(table.columns) == 6
    assert len(table.rows) == 3  # header + 2 items
    header = [cell.text for cell in table.rows[0].cells]
    assert header == ["#", "Description", "Quantity", "Unit", "Unit Price", "Amount"]
    row1 = [cell.text for cell in table.rows[1].cells]
    assert row1[1] == "Deep clean"
    assert row1[2] == "3"
    assert row1[4] == "$150.00"
    assert row1[5] == "$450.00"
    # The {{line_items}} paragraph should be gone and replaced by the table.
    assert "{{line_items}}" not in "".join(p.text for p in doc.paragraphs)


def test_missing_optional_placeholders_do_not_crash():
    docx = _make_docx(["{{customer_company}}", "{{business_tax_id}}", "{{signature}}", "plain"])
    filled = _fill(docx, {})
    doc = Document(io.BytesIO(filled))
    texts = [p.text for p in doc.paragraphs]
    assert "" in texts  # unknown placeholders collapsed to empty strings
    assert "plain" in texts


def test_line_items_placeholder_left_intact_when_no_items():
    docx = _make_docx(["{{line_items}}"])
    filled = _fill(docx, {})
    doc = Document(io.BytesIO(filled))
    assert "{{line_items}}" in doc.paragraphs[0].text


# ── Sample template ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sample_template_download(client):
    await create_user("dcx-sample@example.com")
    await login(client, "dcx-sample@example.com")
    res = await client.get("/api/business-profile/template/sample")
    assert res.status_code == 200
    assert res.headers["content-type"] == DOCX_MIME
    assert res.content[:4] == b"PK\x03\x04"
    assert "quoteflow-sample-template.docx" in res.headers.get("content-disposition", "")


# ── Preview ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_preview_returns_uploaded_docx(client):
    user = await create_user("dcx-prev@example.com")
    await login(client, "dcx-prev@example.com")
    await _profile(user.id)

    docx = _make_docx(["preview me"])
    await _upload(client, "letter.docx", docx, DOCX_MIME)
    res = await client.get("/api/business-profile/template/preview")
    assert res.status_code == 200
    assert res.headers["content-type"] == DOCX_MIME
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.content == docx


@pytest.mark.asyncio
async def test_preview_requires_custom_docx(client):
    user = await create_user("dcx-noprev@example.com")
    await login(client, "dcx-noprev@example.com")
    await _profile(user.id)
    res = await client.get("/api/business-profile/template/preview")
    assert res.status_code == 404


# ── Switching template types ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_switch_from_custom_docx_to_default(client):
    user = await create_user("dcx-switch@example.com")
    await login(client, "dcx-switch@example.com")
    await _profile(user.id)

    await _upload(client, "letter.docx", _valid_docx(), DOCX_MIME)
    assert (await client.get("/api/business-profile/template")).json()["template_type"] == "custom_docx"

    res = await client.post("/api/business-profile/template/default")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template_type"] == "default"
    assert body["custom_docx_file_id"] is not None


@pytest.mark.asyncio
async def test_delete_custom_docx(client):
    user = await create_user("dcx-del@example.com")
    await login(client, "dcx-del@example.com")
    await _profile(user.id)

    await _upload(client, "letter.docx", _valid_docx(), DOCX_MIME)
    res = await client.delete("/api/business-profile/template")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template_type"] == "default"
    assert body["has_custom_template"] is False
    assert body["custom_docx_file_id"] is None
    assert body["custom_docx_filename"] == ""

    res = await client.get("/api/business-profile/template/preview")
    assert res.status_code == 404


# ── Ownership security ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_user_cannot_access_another_business_docx(client):
    a = await create_user("dcx-owner-a@example.com")
    b = await create_user("dcx-owner-b@example.com")
    await _profile(a.id, add_docx=True)  # A has a custom DOCX template
    async with async_session_factory() as db:
        db.add(make_business_profile(b.id))
        await db.commit()

    await login(client, "dcx-owner-b@example.com")
    res = await client.get("/api/business-profile/template")
    assert res.status_code == 200
    body = res.json()
    assert body["template_type"] == "default"
    assert body["has_custom_template"] is False
    assert body["custom_docx_file_id"] is None

    # B cannot preview or test A's template.
    assert (await client.get("/api/business-profile/template/preview")).status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_delete_another_business_docx(client):
    a = await create_user("dcx-del-a@example.com")
    b = await create_user("dcx-del-b@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(b.id))
        await db.commit()
    await _profile(a.id, add_docx=True)

    await login(client, "dcx-del-b@example.com")
    res = await client.delete("/api/business-profile/template")
    assert res.status_code == 200
    assert res.json()["template_type"] == "default"

    async with async_session_factory() as db:
        profile = (await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == a.id))).scalar_one()
        assert profile.template_type == "custom_docx"
        assert profile.custom_docx_file_id is not None


# ── Converter availability / errors ────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_pdf_converter_unavailable_returns_503(client, monkeypatch):
    from app.services import docx_to_pdf

    monkeypatch.setattr(docx_to_pdf, "is_converter_available", lambda: False)

    user = await create_user("dcx-503@example.com")
    await login(client, "dcx-503@example.com")
    await _profile(user.id, add_docx=True, tax_rate_bps=750)

    quote = await _create_quote(client, quote_number="Q-503")
    res = await client.post(f"/api/quotes/{quote['id']}/generate-pdf")
    assert res.status_code == 503
    assert "LibreOffice" in res.json()["detail"]


@pytest.mark.asyncio
async def test_test_template_converter_unavailable_returns_503(client, monkeypatch):
    from app.services import docx_to_pdf

    monkeypatch.setattr(docx_to_pdf, "is_converter_available", lambda: False)

    user = await create_user("dcx-test503@example.com")
    await login(client, "dcx-test503@example.com")
    await _profile(user.id, add_docx=True)

    res = await client.post("/api/business-profile/template/test")
    assert res.status_code == 503


# ── PDF generation with DOCX ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_pdf_default_without_custom_docx(client):
    user = await create_user("dcx-epd@example.com")
    await login(client, "dcx-epd@example.com")
    await _profile(user.id, tax_rate_bps=750)

    quote = await _create_quote(client, quote_number="Q-DCXDF")
    res = await client.post(f"/api/quotes/{quote['id']}/generate-pdf")
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")
    assert res.headers.get("x-quoteflow-template") == "default"
    assert _page_count(res.content) == 1


@pytest.mark.asyncio
async def test_custom_docx_filled_and_converted_to_pdf(client, monkeypatch):
    from app.services import docx_to_pdf

    captured: dict = {}

    def fake_convert(docx_bytes: bytes) -> bytes:
        captured["docx"] = docx_bytes
        return _minimal_pdf()

    monkeypatch.setattr(docx_to_pdf, "is_converter_available", lambda: True)
    monkeypatch.setattr(docx_to_pdf, "convert_docx_to_pdf", fake_convert)

    user = await create_user("dcx-cvt@example.com")
    await login(client, "dcx-cvt@example.com")
    await _profile(user.id, add_docx=True, tax_rate_bps=750)

    quote = await _create_quote(
        client,
        quote_number="Q-DCXC",
        items=[{"description": "Deep clean", "quantity": "3", "unit": "hour", "unit_price": "150.00", "sort_order": 0}],
    )
    res = await client.post(f"/api/quotes/{quote['id']}/generate-pdf")
    assert res.status_code == 200, res.text
    assert res.headers.get("x-quoteflow-template") == "custom_docx"
    assert res.content.startswith(b"%PDF")
    assert _page_count(res.content) == 1

    # The DOCX handed to the converter was filled with quote data and includes
    # one quotation worth of data — not a template-only page.
    filled = Document(io.BytesIO(captured["docx"]))
    texts = [p.text for p in filled.paragraphs]
    assert any("Sparkle Cleaning" in t for t in texts)
    assert all("{{" not in t for t in texts)
    assert len(filled.tables) == 1
    table = filled.tables[0]
    assert len(table.rows) == 2  # header + 1 item
    row1 = [cell.text for cell in table.rows[1].cells]
    assert row1[1] == "Deep clean"
    assert row1[2] == "3"  # quantity remains 3
    assert row1[4] == "$150.00"
    assert row1[5] == "$450.00"


@pytest.mark.asyncio
async def test_custom_docx_failure_falls_back_to_default(client, monkeypatch):
    from app.services import docx_to_pdf

    def fake_convert(docx_bytes: bytes) -> bytes:
        raise RuntimeError("soffice exploded")

    monkeypatch.setattr(docx_to_pdf, "is_converter_available", lambda: True)
    monkeypatch.setattr(docx_to_pdf, "convert_docx_to_pdf", fake_convert)

    user = await create_user("dcx-fall@example.com")
    await login(client, "dcx-fall@example.com")
    await _profile(user.id, add_docx=True, tax_rate_bps=750)

    quote = await _create_quote(client, quote_number="Q-FALL")
    res = await client.post(f"/api/quotes/{quote['id']}/generate-pdf")
    assert res.status_code == 200, res.text
    assert res.headers.get("x-quoteflow-template") == "default"
    assert res.content.startswith(b"%PDF")
    assert "QUOTATION" in res.content.decode("latin-1")


@pytest.mark.asyncio
async def test_ghost_docx_file_on_disk_falls_back_to_default(client):
    """Template metadata exists but the file is missing on disk → default PDF."""
    user = await create_user("dcx-ghost@example.com")
    await login(client, "dcx-ghost@example.com")
    async with async_session_factory() as db:
        profile = make_business_profile(user.id, tax_rate_bps=750)
        db.add(profile)
        await db.flush()
        tf = TemplateFile(
            user_id=user.id,
            stored_name="ghost-docx.docx",
            original_name="ghost.docx",
            content_type=DOCX_MIME,
            size_bytes=10,
        )
        db.add(tf)
        await db.flush()
        profile.template_type = "custom_docx"
        profile.custom_docx_file_id = tf.id
        profile.custom_docx_filename = "ghost.docx"
        profile.custom_docx_mime_type = DOCX_MIME
        profile.custom_docx_size = 10
        profile.custom_docx_uploaded_at = datetime.now(UTC)
        profile.custom_docx_version = 1
        await db.commit()

    quote = await _create_quote(client, quote_number="Q-GHOST")
    res = await client.post(f"/api/quotes/{quote['id']}/generate-pdf")
    assert res.status_code == 200, res.text
    assert res.headers.get("x-quoteflow-template") == "default"
    assert _page_count(res.content) == 1


# ── Regression: quote calculations / ownership unchanged ───────────────
@pytest.mark.asyncio
async def test_quote_calculations_unchanged(client):
    user = await create_user("dcx-calc@example.com")
    await login(client, "dcx-calc@example.com")
    await _profile(user.id, add_docx=True, tax_rate_bps=1200)

    quote = await _create_quote(
        client,
        quote_number="Q-DCXCALC",
        items=[{"description": "Deep clean", "quantity": "3", "unit": "hour", "unit_price": "150.00", "sort_order": 0}],
    )
    assert quote["subtotal_minor"] == 45000
    assert quote["tax_minor"] == 5400
    assert quote["total_minor"] == 50400
    assert quote["items"][0]["quantity"] == "3"


@pytest.mark.asyncio
async def test_quote_ownership_secure_after_docx_upload(client):
    a = await create_user("dcx-own-a@example.com")
    await create_user("dcx-own-b@example.com")
    async with async_session_factory() as db:
        db.add(make_business_profile(a.id, tax_rate_bps=750))
        await db.commit()

    await login(client, "dcx-own-a@example.com")
    quote = await _create_quote(client, quote_number="Q-OWND")

    await login(client, "dcx-own-b@example.com")
    res = await client.get(f"/api/quotes/{quote['id']}")
    assert res.status_code == 404
    res = await client.get("/api/business-profile/template")
    assert res.status_code == 404  # B has no profile
