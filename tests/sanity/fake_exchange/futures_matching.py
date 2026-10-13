"""`EPIC-039C` — which resting Futures orders a price makes trade, and what a
reduce-only order may do.

@details The mirror of `spot_order_book.py`'s rules, at the order's own limit price
(never a better one: a price that gapped through the limit still fills at the limit):
a `LIMIT` buy trades once the price is at or below its limit, a sell once it is at or
above. A reduce-only order may only trade against a position on the other side, and
never for more than the position holds.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

_BUY = "BUY"
_LIMIT = "LIMIT"


def crosses(order: dict[str, Any], price: Decimal) -> bool:
    """Whether `price` makes the resting `order` trade."""
    if order["type"] != _LIMIT:
        return False
    limit = Decimal(order["price"])
    return price <= limit if order["side"] == _BUY else price >= limit


def reduces(held: Decimal, side: str) -> bool:
    """Whether an order on `side` would reduce the signed position `held`."""
    return held < 0 if side == _BUY else held > 0


def remaining(order: dict[str, Any]) -> Decimal:
    return Decimal(order["origQty"]) - Decimal(order["executedQty"])
