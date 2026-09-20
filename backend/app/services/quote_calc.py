"""Central quote calculation engine.

All money is handled as Decimal during calculation and stored as integer minor
units (cents). Total values submitted by the frontend are never trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import bad_request

DECIMAL_ONE = Decimal("1")
HUNDRED = Decimal("100")


def is_zero(v: Decimal) -> bool:
    return v == 0


@dataclass
class CalculatedLine:
    description: str
    quantity: str
    unit: str
    unit_price_minor: int
    line_total_minor: int
    sort_order: int


@dataclass
class CalculationResult:
    subtotal_minor: int = 0
    discount_minor: int = 0
    tax_minor: int = 0
    total_minor: int = 0
    tax_rate_bps: int = 0
    taxable_minor: int = 0
    lines: list[CalculatedLine] = field(default_factory=list)

    @property
    def breakdown(self) -> dict:
        return {
            "subtotal_minor": self.subtotal_minor,
            "discount_minor": self.discount_minor,
            "tax_minor": self.tax_minor,
            "total_minor": self.total_minor,
            "taxable_minor": self.taxable_minor,
            "tax_rate_percent": format_decimal(tax_bps_to_percent(self.tax_rate_bps)),
        }


def tax_bps_to_percent(bps: int) -> Decimal:
    return (Decimal(bps) / Decimal(10000) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def format_decimal(value: Decimal) -> str:
    """Return a normalized decimal string, e.g. '149.50' or '0'."""
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    return f"{value:.2f}"


def format_percent(bps: int) -> str:
    """Format basis points as a percentage string with no trailing zeros.

    750 -> '7.5', 725 -> '7.25', 0 -> '0'.
    """
    s = str(Decimal(bps) / Decimal(100))
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def tax_rate_bps_from_percent(percent_str: str) -> int:
    """Parse a user-configured tax rate percentage string into basis points.

    '7.5' -> 750, '0' -> 0, '15' -> 1500. Rejects negatives and absurd values.
    """
    try:
        percent = Decimal(percent_str.strip())
    except Exception:
        raise bad_request("Tax rate must be a number between 0 and 50.") from None
    if percent < 0 or percent > 50:
        raise bad_request("Tax rate must be between 0 and 50 percent.")
    bps = int((percent * Decimal(100)).quantize(DECIMAL_ONE, rounding=ROUND_HALF_UP))
    return bps


def calculate_line_total_minor(quantity: str, unit_price_minor: int) -> int:
    """line_total = quantity * unit_price, rounded to nearest cent."""
    try:
        qty = Decimal(quantity.strip())
    except Exception:
        raise bad_request(f"Invalid quantity: {quantity!r}") from None
    if qty <= 0:
        raise bad_request("Quantity must be greater than zero.")
    if qty > Decimal("1000000000"):
        raise bad_request("Quantity out of range.")
    line = qty * unit_price_minor
    return int(line.quantize(DECIMAL_ONE, rounding=ROUND_HALF_UP))


def calculate_quote(
    items: list[dict],
    discount_minor: int,
    tax_rate_bps: int,
) -> CalculationResult:
    """Calculate subtotal / discount / tax / total.

    items: list of dicts with keys description, quantity, unit, unit_price_minor, sort_order.
    """
    if not items:
        raise bad_request("A quote must contain at least one item.")
    if len(items) > 50:
        raise bad_request("A quote cannot contain more than 50 items.")

    lines: list[CalculatedLine] = []
    subtotal = Decimal(0)
    for raw in items:
        unit_price = raw.get("unit_price_minor", 0)
        if not isinstance(unit_price, int) or unit_price < 0:
            raise bad_request("Unit price must be a non-negative whole number of cents.")
        if unit_price > 1_000_000_000:
            raise bad_request("Unit price out of range.")
        line_total = calculate_line_total_minor(str(raw["quantity"]), unit_price)
        if line_total < 0:
            raise bad_request("Line totals cannot be negative.")
        subtotal += line_total
        lines.append(
            CalculatedLine(
                description=str(raw.get("description", "")),
                quantity=str(raw["quantity"]),
                unit=str(raw.get("unit", "")),
                unit_price_minor=unit_price,
                line_total_minor=line_total,
                sort_order=int(raw.get("sort_order", 0)),
            )
        )

    subtotal_minor = int(subtotal)

    if discount_minor < 0:
        raise bad_request("Discount cannot be negative.")
    if discount_minor > subtotal_minor:
        raise bad_request("Discount cannot exceed the subtotal.")

    taxable_amount = subtotal_minor - discount_minor
    taxable_minor = int(taxable_amount)
    if tax_rate_bps < 0 or tax_rate_bps > 5000:
        raise bad_request("Configured tax rate is out of range.")
    tax_decimal = (Decimal(taxable_amount) * Decimal(tax_rate_bps) / Decimal(10000)).quantize(
        DECIMAL_ONE, rounding=ROUND_HALF_UP
    )
    tax_minor = int(tax_decimal)
    total_minor = taxable_amount + tax_minor

    return CalculationResult(
        subtotal_minor=subtotal_minor,
        discount_minor=discount_minor,
        tax_minor=tax_minor,
        total_minor=total_minor,
        tax_rate_bps=tax_rate_bps,
        taxable_minor=taxable_minor,
        lines=lines,
    )
