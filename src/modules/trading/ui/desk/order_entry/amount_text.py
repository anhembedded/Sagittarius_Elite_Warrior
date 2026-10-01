"""`EPIC-028H` — how the order panel writes an amount: no exponent, no
trailing zeros, grouped by thousands; a dash when unknown."""

from __future__ import annotations

from decimal import Decimal

NONE_TEXT = "—"


def format_amount(value: Decimal | None) -> str:
    if value is None:
        return NONE_TEXT
    return f"{value.normalize():,f}"
