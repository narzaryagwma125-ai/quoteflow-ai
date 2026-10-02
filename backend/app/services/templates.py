"""Custom quotation template helpers shared by API routes and PDF generation."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.business_profile import BusinessProfile
from app.schemas.business import TemplateSettings
from app.uploads.store import read_template


def build_settings(profile: BusinessProfile) -> TemplateSettings:
    """Build the public template settings for a business profile.

    Uses the joined-loaded ``custom_docx_file`` relationship to verify the
    file row actually exists on disk — safe metadata alone is never trusted.
    """
    template_file = profile.custom_docx_file if profile.custom_docx_file_id else None
    file_configured = bool(profile.custom_docx_file_id and profile.custom_docx_filename)
    file_present = template_file is not None and bool(template_file.stored_name)
    return TemplateSettings(
        template_type=profile.template_type,
        custom_docx_file_id=profile.custom_docx_file_id,
        custom_docx_filename=profile.custom_docx_filename,
        custom_docx_mime_type=profile.custom_docx_mime_type,
        custom_docx_size=profile.custom_docx_size,
        custom_docx_uploaded_at=profile.custom_docx_uploaded_at,
        custom_docx_version=profile.custom_docx_version,
        has_custom_template=file_configured and file_present,
    )


def load_custom_docx(profile: BusinessProfile) -> bytes | None:
    """Return the raw custom DOCX bytes when a custom DOCX template is active.

    Returns ``None`` when no template is configured, the file row is missing,
    or the file is missing on disk — in every case the caller falls back to the
    default QuoteFlow template.
    """
    if profile.template_type != "custom_docx":
        return None
    if not profile.custom_docx_file_id:
        return None
    template_file = profile.custom_docx_file
    if template_file is None or not template_file.stored_name:
        return None
    return read_template(template_file.stored_name)


def now_utc() -> datetime:
    return datetime.now(UTC)
