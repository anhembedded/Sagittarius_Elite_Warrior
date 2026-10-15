"""`BUG-210` — how the Grid editor shows what a field holds and what a verdict about it means.

Held apart from `grid_panel.py` (the widgets) because each is a small decision the panel only
applies: which stock icon a severity wears, how a price reads, where a suggested price lands.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from PySide6.QtWidgets import QStyle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice import plain


def marker_icon(blocks: bool) -> QStyle.StandardPixmap:
    """Severity to icon, the one place (`BUG-210`): the stop sign for what blocks Start;
    advice does not block, so it is information, not a warning triangle."""
    return (
        QStyle.StandardPixmap.SP_MessageBoxCritical
        if blocks
        else QStyle.StandardPixmap.SP_MessageBoxInformation
    )


def price_text(price: Decimal | str) -> str:
    """A price as the person would type it: `2371.98`, not `2371.98000000`. Text that is not a
    number stays as typed, for the parameters check to name."""
    try:
        value = Decimal(price)
    except InvalidOperation:
        return str(price)
    return plain(value) if value.is_finite() else str(price)


def snap_to_tick(price: Decimal, tick: Decimal | None) -> Decimal:
    """`price` on the nearest tick; unchanged while the tick is not known."""
    if tick is None or tick <= 0:
        return price
    return (price / tick).quantize(Decimal(1), rounding=ROUND_HALF_UP) * tick
