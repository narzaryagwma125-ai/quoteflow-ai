from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field


class PublicQuoteItem(BaseModel):
    description: str
    quantity: str
    unit: str
    unit_price_minor: int
    line_total_minor: int


class PublicQuoteResponse(BaseModel):
    business_name: str = ""
    quote_number: str
    status: str
    issue_date: date
    expiry_date: date | None
    currency: str
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    notes: str
    terms: str
    items: list[PublicQuoteItem]
    may_respond: bool


class PublicQuoteRespond(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
