from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BusinessProfileCreate(BaseModel):
    business_name: str = Field(min_length=1, max_length=200)
    owner_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    address_line_1: str = Field(default="", max_length=255)
    address_line_2: str = Field(default="", max_length=255)
    city: str = Field(default="", max_length=120)
    state_or_province: str = Field(default="", max_length=120)
    postal_code: str = Field(default="", max_length=20)
    country: str = Field(default="US", min_length=2, max_length=2)
    currency: str = Field(default="INR", pattern="^(USD|CAD|INR|GBP|AUD)$")
    timezone: str = Field(default="America/New_York", max_length=64)
    tax_rate: str = Field(default="0", max_length=20)  # percent, user-configured (e.g. "7.5")

    @field_validator("business_name", "owner_name")
    @classmethod
    def strip_named(cls, v: str) -> str:
        return v.strip()


class BusinessProfileUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=200)
    owner_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state_or_province: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    currency: str | None = Field(default=None, pattern="^(USD|CAD|INR|GBP|AUD)$")
    timezone: str | None = Field(default=None, max_length=64)
    tax_rate: str | None = Field(default=None, max_length=20)
    logo_position: Literal["left", "center", "right"] | None = None
    logo_size: Literal["small", "medium", "large"] | None = None
    show_logo_on_quotation: bool | None = None


class BusinessProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_name: str
    owner_name: str
    email: str
    phone: str
    address_line_1: str
    address_line_2: str
    city: str
    state_or_province: str
    postal_code: str
    country: str
    currency: str
    timezone: str
    tax_rate_percent: str
    tax_rate_unconfigured: bool
    has_logo: bool
    logo_position: str
    logo_size: str
    show_logo_on_quotation: bool
    created_at: datetime


class LogoResponse(BaseModel):
    id: int
    content_type: str
    size_bytes: int


class TemplateSettings(BaseModel):
    """Current quotation template configuration for a business profile."""

    template_type: Literal["default", "custom_docx"]
    custom_docx_file_id: int | None = None
    custom_docx_filename: str = ""
    custom_docx_mime_type: str = ""
    custom_docx_size: int = 0
    custom_docx_uploaded_at: datetime | None = None
    custom_docx_version: int = 0
    # True when the custom DOCX was set but its file is missing on disk so
    # PDF generation will fall back to the default template.
    has_custom_template: bool = False
