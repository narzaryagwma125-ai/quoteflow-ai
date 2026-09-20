from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_origin
from app.core.errors import not_found, service_unavailable
from app.db.session import get_db
from app.models.business_profile import BusinessProfile, TemplateFile
from app.models.user import User
from app.schemas.business import TemplateSettings
from app.security.rate_limit import client_ip_key, enforce
from app.services.audit import audit
from app.services.docx_templates import build_sample_docx, fill_docx_template
from app.services.docx_to_pdf import (
    DocxConversionUnavailable,
    convert_docx_to_pdf,
    is_converter_available,
)
from app.services.templates import build_settings, now_utc
from app.uploads.store import (
    DOCX_MIME_TYPE,
    delete_template,
    read_template,
    safe_original_name,
    store_template,
    validate_template,
)

logger = logging.getLogger("quoteflow")

router = APIRouter(prefix="/api/business-profile/template", tags=["business", "templates"])

_SAMPLE_VALUES = {
    "business_name": "Sparkle Cleaning",
    "business_owner": "Alex Sparks",
    "business_email": "alex@sparkle.example",
    "business_phone": "555-0100",
    "business_address": "10 Maple St\nSpringfield, IL 62704",
    "business_tax_id": "",
    "business_currency": "USD",
    "quote_number": "Q-2026-0001",
    "issue_date": "September 13, 2026",
    "valid_until": "October 13, 2026",
    "status": "SENT",
    "currency": "USD",
    "customer_name": "Jane Doe",
    "customer_company": "",
    "customer_email": "jane@example.com",
    "customer_phone": "555-0199",
    "customer_address": "42 Oak Ave\nAustin, TX",
    "subtotal": "$450.00",
    "discount": "$0.00",
    "tax_rate": "7.5%",
    "tax_amount": "$33.75",
    "total": "$483.75",
    "notes": "Thank you for your interest.",
    "payment_terms": "Payment due within 14 days.",
    "signature": "Alex Sparks",
}

_SAMPLE_ITEMS = [
    {"description": "Deep house cleaning", "quantity": "3", "unit": "hour",
     "unit_price_minor": 15000, "line_total_minor": 45000},
]


async def _get_profile(db: AsyncSession, user_id: int) -> BusinessProfile:
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is None:
        raise not_found("Business profile not found. Create one first.")
    return profile


@router.get("", response_model=TemplateSettings)
async def get_template_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateSettings:
    profile = await _get_profile(db, user.id)
    return build_settings(profile)


@router.post("", response_model=TemplateSettings)
async def upload_custom_template(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateSettings:
    verify_origin(request)
    await enforce(client_ip_key(request), "template_upload", limit=10, window_seconds=3600)

    profile = await _get_profile(db, user.id)

    content_type, data, size = validate_template(file)
    original_name = safe_original_name(file.filename, "template.docx")

    template_file = TemplateFile(
        user_id=user.id,
        stored_name="",
        original_name=original_name,
        content_type=content_type,
        size_bytes=size,
    )
    db.add(template_file)
    await db.flush()

    stored_path = store_template(content_type, data)
    template_file.stored_name = stored_path.name

    if profile.custom_docx_file_id:
        old = await db.get(TemplateFile, profile.custom_docx_file_id)
        if old is not None:
            if old.user_id != user.id:
                raise not_found("Template not found.")
            if old.stored_name:
                delete_template(old.stored_name)
            await db.delete(old)
            await db.flush()

    profile.template_type = "custom_docx"
    profile.custom_docx_file_id = template_file.id
    profile.custom_docx_filename = original_name
    profile.custom_docx_mime_type = content_type
    profile.custom_docx_size = size
    profile.custom_docx_uploaded_at = now_utc()
    profile.custom_docx_version += 1

    await audit(db, "business_profile.template_uploaded", user_id=user.id, entity_type="business_profile")
    await db.commit()
    await db.refresh(profile)
    return build_settings(profile)


@router.get("/sample")
async def download_sample_template(
    user: User = Depends(get_current_user),
) -> Response:
    """Download a sample DOCX template containing every supported placeholder."""
    data = build_sample_docx()
    return Response(
        content=data,
        media_type=DOCX_MIME_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="quoteflow-sample-template.docx"',
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/test")
async def test_custom_template(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Fill the stored DOCX with sample data and convert it to PDF for preview."""
    verify_origin(request)
    profile = await _get_profile(db, user.id)
    if not profile.custom_docx_file_id:
        raise not_found("No custom DOCX template uploaded.")

    template_file = profile.custom_docx_file
    if template_file is None or not template_file.stored_name:
        raise not_found("Custom DOCX file is missing on disk.")
    if template_file.user_id != user.id:
        raise not_found("Template not found.")

    data = read_template(template_file.stored_name)
    if data is None:
        raise not_found("Custom DOCX file is missing on disk.")

    if not is_converter_available():
        raise service_unavailable(
            "DOCX-to-PDF conversion requires LibreOffice to be installed on the server. "
            "You can still keep the template; default QuoteFlow PDFs continue to work."
        )

    try:
        filled = fill_docx_template(data, dict(_SAMPLE_VALUES), items=_SAMPLE_ITEMS)
        pdf_bytes = convert_docx_to_pdf(filled)
    except DocxConversionUnavailable:
        raise service_unavailable(
            "DOCX-to-PDF conversion requires LibreOffice to be installed on the server."
        ) from None
    except Exception:
        logger.exception(
            "Test DOCX template conversion failed for user %s; running default fallback.",
            user.id,
        )
        raise service_unavailable(
            "The DOCX template could not be converted to PDF. "
            "Check the template and try again, or use the default template."
        ) from None

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="template-preview.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/preview")
async def preview_custom_template(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    profile = await _get_profile(db, user.id)
    if not profile.custom_docx_file_id:
        raise not_found("No custom DOCX template uploaded.")
    template_file = profile.custom_docx_file
    if template_file is None or not template_file.stored_name:
        raise not_found("Custom DOCX file is missing on disk.")
    if template_file.user_id != user.id:
        raise not_found("Template not found.")
    data = read_template(template_file.stored_name)
    if data is None:
        raise not_found("Custom DOCX file is missing on disk.")
    return Response(
        content=data,
        media_type=template_file.content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.post("/default", response_model=TemplateSettings)
async def set_default_template(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateSettings:
    verify_origin(request)
    profile = await _get_profile(db, user.id)
    profile.template_type = "default"
    await audit(db, "business_profile.template_set_default", user_id=user.id, entity_type="business_profile")
    await db.commit()
    await db.refresh(profile)
    return build_settings(profile)


@router.post("/custom-docx", response_model=TemplateSettings)
async def use_custom_docx_template(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateSettings:
    """Re-activate the stored custom DOCX after previously switching to default."""
    verify_origin(request)
    profile = await _get_profile(db, user.id)
    if not profile.custom_docx_file_id:
        raise not_found("Upload a custom DOCX template first.")
    profile.template_type = "custom_docx"
    await audit(db, "business_profile.template_use_custom_docx", user_id=user.id, entity_type="business_profile")
    await db.commit()
    await db.refresh(profile)
    return build_settings(profile)


@router.delete("", response_model=TemplateSettings)
async def delete_custom_template(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateSettings:
    verify_origin(request)
    profile = await _get_profile(db, user.id)

    if profile.custom_docx_file_id:
        template_file = await db.get(TemplateFile, profile.custom_docx_file_id)
        if template_file is not None:
            if template_file.user_id != user.id:
                raise not_found("Template not found.")
            if template_file.stored_name:
                delete_template(template_file.stored_name)
            await db.delete(template_file)
            await db.flush()

    profile.template_type = "default"
    profile.custom_docx_file_id = None
    profile.custom_docx_filename = ""
    profile.custom_docx_mime_type = ""
    profile.custom_docx_size = 0
    profile.custom_docx_uploaded_at = None
    profile.custom_docx_version = 0

    await audit(db, "business_profile.template_deleted", user_id=user.id, entity_type="business_profile")
    await db.commit()
    await db.refresh(profile)
    return build_settings(profile)
