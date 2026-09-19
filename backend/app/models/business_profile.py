from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CURRENCIES = ("USD", "CAD", "INR", "GBP", "AUD")

TEMPLATE_TYPES = ("default", "custom_docx")


class LogoFile(Base):
    __tablename__ = "logo_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stored_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


class TemplateFile(Base):
    __tablename__ = "template_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stored_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    address_line_2: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    state_or_province: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")
    # Tax rate stored as integer basis points (percent * 100) to avoid float money.
    # e.g. 7.5%  -> 750. User-configured, never hardcoded per country.
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    logo_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("logo_files.id", ondelete="SET NULL"), nullable=True
    )
    # Custom quotation template configuration. A value of "default" means quote
    # PDFs use the built-in professional QuoteFlow template; "custom_docx" means
    # the uploaded DOCX file is filled with quote data and converted to PDF.
    template_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="default", server_default="default"
    )
    # Legacy PDF/PNG/JPG template columns — preserved in the database for data
    # safety but no longer used by new code (replaced by custom_docx_*).
    custom_template_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("template_files.id", ondelete="SET NULL"), nullable=True
    )
    custom_template_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    custom_template_mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    custom_template_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    custom_template_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    custom_template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # DOCX custom quotation template.
    custom_docx_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("template_files.id", ondelete="SET NULL"), nullable=True
    )
    custom_docx_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    custom_docx_mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    custom_docx_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    custom_docx_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    custom_docx_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Logo display settings for generated quotations.  "left"/"center"/"right"
    # position the logo in the DOCX header; "small"/"medium"/"large" control its
    # height.  show_logo_on_quotation gates whether any logo is embedded.
    logo_position: Mapped[str] = mapped_column(
        String(10), nullable=False, default="left", server_default="left"
    )
    logo_size: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium", server_default="medium"
    )
    show_logo_on_quotation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    user = relationship("User", back_populates="business_profiles")
    logo_file = relationship("LogoFile", lazy="joined", foreign_keys=[logo_file_id])
    custom_template_file = relationship(
        "TemplateFile", lazy="joined", foreign_keys=[custom_template_file_id]
    )
    custom_docx_file = relationship(
        "TemplateFile", lazy="joined", foreign_keys=[custom_docx_file_id]
    )
