"""`EPIC-028H` — how the order panel writes an amount (no exponent, no
trailing zeros, grouped by thousands; a dash when unknown) and reads one
back."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

NONE_TEXT = "—"


def format_amount(value: Decimal | None) -> str:
    if value is None:
        return NONE_TEXT
    return f"{value.normalize():,f}"


def parse_amount(text: str) -> Decimal | None:
    """@return `text` as a finite, non-negative `Decimal`, or `None`.
    Thousands separators are accepted, because the panel shows them."""
    try:
        value = Decimal(text.replace(",", "").strip())
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    return value
