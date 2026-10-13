"""`EPIC-039D` — how one fill moves an owner's signed position.

@details One formula, used by the position book as fills arrive and by the
deriver as it replays the venue's history, so the two can never disagree
(the `owner_inventory_policy.py` rule):

- a fill on the position's side (or into a flat one) adds to it, and the
  average entry becomes the weighted average;
- a fill against it closes up to what is held at a profit of
  `(fill price − entry)` per unit for a long, `(entry − fill price)` for a
  short; a **reduce** leaves the average entry as it was;
- a fill larger than what is held **flips** the position: the remainder
  enters at the fill's price;
- a position back to zero has no entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
)

_ZERO = Decimal(0)


@dataclass(frozen=True)
class PositionFill:
    """One fill of an owner's order, as the position sees it."""

    side: OrderSide
    #: The base this fill traded; positive.
    quantity: Decimal
    price: Decimal
    #: The commission charged in the quote asset; zero when none or in another asset.
    quote_fee: Decimal = _ZERO


def position_after(position: OwnerPosition, fill: PositionFill) -> OwnerPosition:
    """@brief `position` once `fill` has happened."""
    signed = fill.quantity if fill.side is OrderSide.BUY else -fill.quantity
    fees = position.fees + fill.quote_fee
    entry = position.average_entry
    if entry is None:
        return OwnerPosition(signed, fill.price, position.realized_pnl, fees)
    held = position.quantity
    total = held + signed
    if (held > 0) == (signed > 0):
        cost = abs(held) * entry + fill.quantity * fill.price
        return OwnerPosition(total, cost / abs(total), position.realized_pnl, fees)
    closed = min(abs(held), fill.quantity)
    per_unit = fill.price - entry
    realized = position.realized_pnl + closed * (per_unit if held > 0 else -per_unit)
    if total == 0:
        return OwnerPosition(_ZERO, None, realized, fees)
    flipped = (total > 0) != (held > 0)
    return OwnerPosition(total, fill.price if flipped else entry, realized, fees)
