from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict

MAX_PAGE_SIZE = 100

CURRENCY_CODES = ("USD", "CAD", "INR", "GBP", "AUD")


def _to_decimal(v) -> Decimal:
    """Normalize input to Decimal via str to avoid float artifacts (e.g. 149.99 -> 149.98999)."""
    if isinstance(v, float):
        return Decimal(str(v))
    return Decimal(v)


def _validate_money(v: Decimal) -> Decimal:
    v = _to_decimal(v)
    if v.is_nan() or v.is_infinite():
        raise ValueError("Invalid monetary value.")
    if v < 0:
        raise ValueError("Money values cannot be negative.")
    if abs(v) >= Decimal("1000000000"):
        raise ValueError("Money value out of range.")
    # limit to 2 decimal places (minor units)
    q = v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if q != v:
        raise ValueError("Money values support at most 2 decimal places.")
    return v


def _validate_positive_quantity(v: Decimal) -> Decimal:
    v = _to_decimal(v)
    if v.is_nan() or v.is_infinite() or v <= 0:
        raise ValueError("Quantity must be a positive number.")
    if v > Decimal("1000000000"):
        raise ValueError("Quantity out of range.")
    return v


Money = Annotated[Decimal, AfterValidator(_validate_money)]
PositiveQuantity = Annotated[Decimal, AfterValidator(_validate_positive_quantity)]


def decimal_to_minor(value: Decimal) -> int:
    """Convert a Decimal dollar amount to integer minor units (cents)."""
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def minor_to_decimal(minor: int) -> Decimal:
    return (Decimal(minor) / 100).quantize(Decimal("0.01"))


CurrencyCode = Literal["USD", "CAD", "INR", "GBP", "AUD"]


class Paginated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list
    total: int
    page: int
    page_size: int


class Timestamped(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: object | None = None
    updated_at: object | None = None
