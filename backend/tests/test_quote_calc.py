"""Unit tests for the central money engine."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.quote_calc import (
    calculate_line_total_minor,
    calculate_quote,
    tax_rate_bps_from_percent,
)


def _items(*pairs):
    """pairs of (description, quantity, unit_price_minor)."""
    return [
        {"description": d, "quantity": str(q), "unit": "", "unit_price_minor": p, "sort_order": i}
        for i, (d, q, p) in enumerate(pairs)
    ]


def test_whole_numbers():
    calc = calculate_quote(_items(("clean", "2", 5000)), discount_minor=0, tax_rate_bps=0)
    assert calc.subtotal_minor == 10000
    assert calc.tax_minor == 0
    assert calc.total_minor == 10000


def test_decimal_quantities():
    calc = calculate_quote(_items(("hourly", "2.5", 4000)), discount_minor=0, tax_rate_bps=0)
    assert calc.subtotal_minor == 10000
    assert calc.lines[0].line_total_minor == 10000


def test_zero_tax():
    calc = calculate_quote(_items(("clean", "1", 10000)), discount_minor=0, tax_rate_bps=0)
    assert calc.tax_minor == 0
    assert calc.total_minor == 10000


def test_discount():
    calc = calculate_quote(
        _items(("clean", "1", 10000)), discount_minor=1500, tax_rate_bps=0
    )
    assert calc.subtotal_minor == 10000
    assert calc.discount_minor == 1500
    assert calc.total_minor == 8500


def test_tax_applies_after_discount():
    calc = calculate_quote(
        _items(("clean", "1", 10000)), discount_minor=2000, tax_rate_bps=750
    )
    assert calc.taxable_minor == 8000
    assert calc.tax_minor == 600
    assert calc.total_minor == 8600


def test_tax_without_discount():
    calc = calculate_quote(_items(("clean", "1", 10000)), discount_minor=0, tax_rate_bps=750)
    assert calc.tax_minor == 750
    assert calc.total_minor == 10750


def test_rounding_half_up():
    # 3 items at 99.99 each -> 299.97; 7.5% of 29997 = 2249.775 -> rounds to 2250
    calc = calculate_quote(
        _items(("x", "3", 9999)), discount_minor=0, tax_rate_bps=750
    )
    assert calc.subtotal_minor == 29997
    assert calc.tax_minor == 2250
    assert calc.total_minor == 32247


def test_large_values():
    calc = calculate_quote(
        _items(("big", "1000", 1000000)), discount_minor=0, tax_rate_bps=5000
    )
    assert calc.subtotal_minor == 1_000_000_000
    assert calc.total_minor == 1_500_000_000


def test_line_total_rounding():
    # 0.333 * $1.00 = 33.3 cents -> rounds to 33
    line = calculate_line_total_minor("0.333", 100)
    assert line == 33


def test_invalid_negative_quantity():
    with pytest.raises(Exception):  # noqa: B017
        calculate_quote(_items(("x", "-1", 1000)), discount_minor=0, tax_rate_bps=0)


def test_invalid_negative_price():
    with pytest.raises(Exception):  # noqa: B017
        calculate_quote(
            [{"description": "x", "quantity": "1", "unit": "", "unit_price_minor": -5, "sort_order": 0}],
            discount_minor=0,
            tax_rate_bps=0,
        )


def test_discount_greater_than_subtotal_rejected():
    with pytest.raises(Exception):  # noqa: B017
        calculate_quote(_items(("x", "1", 1000)), discount_minor=2000, tax_rate_bps=0)


def test_empty_items_rejected():
    with pytest.raises(Exception):  # noqa: B017
        calculate_quote([], discount_minor=0, tax_rate_bps=0)


def test_more_than_50_items_rejected():
    items = [{"description": f"i{i}", "quantity": "1", "unit": "", "unit_price_minor": 1, "sort_order": i} for i in range(51)]
    with pytest.raises(Exception):  # noqa: B017
        calculate_quote(items, discount_minor=0, tax_rate_bps=0)


def test_tax_rate_parse():
    assert tax_rate_bps_from_percent("7.5") == 750
    assert tax_rate_bps_from_percent("0") == 0
    assert tax_rate_bps_from_percent("15") == 1500
    assert tax_rate_bps_from_percent(" 13.25 ") == 1325
    with pytest.raises(Exception):  # noqa: B017
        tax_rate_bps_from_percent("-1")
    with pytest.raises(Exception):  # noqa: B017
        tax_rate_bps_from_percent("51")


def test_currency_formatting():
    # minor_to_decimal is defined in schemas.common; ensure the helper path is consistent
    from app.schemas.common import minor_to_decimal

    assert minor_to_decimal(14999) == Decimal("149.99")
    assert minor_to_decimal(0) == Decimal("0.00")
    assert minor_to_decimal(150) == Decimal("1.50")
