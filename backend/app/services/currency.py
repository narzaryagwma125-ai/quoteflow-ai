"""Supported currencies and symbol rendering.

Single source of truth for which ISO currency codes QuoteFlow accepts and how
their display symbols are derived. Unknown codes (e.g. a currency imported from
an older record) fall back to the ISO code so amounts are never mislabelled.
"""

from __future__ import annotations

SUPPORTED_CURRENCIES = ("USD", "CAD", "INR", "GBP", "AUD")

CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "CAD": "CA$",
    "INR": "\u20b9",  # ₹
    "GBP": "\u00a3",  # £
    "AUD": "A$",
}


def currency_symbol(currency: str) -> str:
    """Display symbol for a currency code, falling back to the ISO code."""
    return CURRENCY_SYMBOLS.get(currency, f"{currency.upper()} ")
