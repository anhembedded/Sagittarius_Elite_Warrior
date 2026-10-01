"""`EPIC-028J` — the order that closes a Futures position at market.

@details A position is closed by an order, never by acting on the position
itself: the opposite side, the position's whole size, `reduce_only` so the
exchange refuses it if the position has already shrunk or flipped (it can
never open one the other way). The caller passes the position it has just
read from the venue, never a row it remembers: the size on screen may be a
fill out of date, and `reduce_only` only caps an order at the position it
finds, it does not grow one to match.

The order goes through `IOrderSubmission.submit`, so every safety gate and
the app's limits apply to it as to any order.

Plausible extensions, each one function here:
- a partial close (a quantity under the position's size);
- a close at a limit price (`OrderType.LIMIT` and a `time_in_force`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType


def market_close_order_for(position: LivePosition) -> OrderRequest:
    """@return A reduce-only market order for the whole of `position`, on
    the opposite side, judged at its mark price."""
    side = OrderSide.SELL if position.position_amt > 0 else OrderSide.BUY
    return OrderRequest(
        symbol=position.symbol,
        side=side,
        order_type=OrderType.MARKET,
        quantity=abs(position.position_amt),
        reference_price=position.mark_price,
        reduce_only=True,
    )
