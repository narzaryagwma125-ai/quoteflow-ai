from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import (
    CurrencyCode,
    Money,
    PositiveQuantity,
    decimal_to_minor,
)

QUOTE_STATUSES = ("draft", "sent", "viewed", "accepted", "rejected", "expired", "cancelled")
MAX_QUOTE_ITEMS = 50


class QuoteItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    quantity: PositiveQuantity
    unit: str = Field(default="", max_length=20)
    unit_price: Money  # dollars, e.g. "149.99"
    sort_order: int = Field(default=0, ge=0, le=10000)

    @property
    def unit_price_minor(self) -> int:
        return decimal_to_minor(self.unit_price)


class QuoteCreate(BaseModel):
    customer_id: int | None = None
    quote_number: str | None = Field(default=None, min_length=1, max_length=40)
    issue_date: date
    expiry_date: date | None = None
    currency: CurrencyCode = "INR"
    discount: Money = Field(default=Decimal("0"))  # dollars
    notes: str = Field(default="", max_length=10000)
    terms: str = Field(default="", max_length=10000)
    items: list[QuoteItemIn] = Field(min_length=1, max_length=MAX_QUOTE_ITEMS)

    @field_validator("issue_date")
    @classmethod
    def validate_issue_date(cls, v: date) -> date:
        # allow backdating for imported quotes; reject obviously wrong years
        if v.year < 2000 or v.year > 2100:
            raise ValueError("issue_date out of range")
        return v

    @property
    def discount_minor(self) -> int:
        return decimal_to_minor(self.discount)


class QuoteUpdate(BaseModel):
    customer_id: int | None = None
    quote_number: str | None = Field(default=None, min_length=1, max_length=40)
    issue_date: date | None = None
    expiry_date: date | None = None
    currency: CurrencyCode | None = None
    discount: Money | None = None
    notes: str | None = Field(default=None, max_length=10000)
    terms: str | None = Field(default=None, max_length=10000)
    items: list[QuoteItemIn] | None = Field(default=None, min_length=1, max_length=MAX_QUOTE_ITEMS)

    @property
    def discount_minor(self) -> int:
        return decimal_to_minor(self.discount) if self.discount is not None else 0


class QuoteItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    quantity: str
    unit: str
    unit_price_minor: int
    line_total_minor: int
    sort_order: int


class QuoteBreakdown(BaseModel):
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    tax_rate_percent: str


class QuotePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quote_number: str
    customer_id: int | None
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
    created_at: datetime
    updated_at: datetime
    items: list[QuoteItemPublic]
    breakdown: QuoteBreakdown | None = None
    customer_name: str = ""
    public_link_token: str = ""
    has_public_link: bool = False


class QuoteListPublic(QuotePublic):
    items: list[QuoteItemPublic] = []


class QuoteResponse(BaseModel):
    quote: QuotePublic
    public_link: str | None = None


class QuotePage(BaseModel):
    items: list[QuotePublic]
    total: int


class CurrencyTotal(BaseModel):
    """Aggregated amounts for a single quote currency (minor units)."""

    currency: str
    currency_symbol: str
    count: int
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int


class QuoteStats(BaseModel):
    """Dashboard summary derived entirely from the quotes table."""

    draft: int
    sent: int
    viewed: int
    accepted: int
    rejected: int
    expired: int
    cancelled: int
    total: int
    created_this_month: int
    totals_by_currency: list[CurrencyTotal]


class QuoteCounter(BaseModel):
    used: int
    limit: int
    remaining: int
