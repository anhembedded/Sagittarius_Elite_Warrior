"""`EPIC-028J` — the order that closes a Futures position at market.

@details A position is closed by an order, never by acting on the position
itself: the opposite side, the position's whole size, `reduce_only` so the
exchange refuses it if the position has already shrunk or flipped (it can
never open one the other way). The caller passes the position it has just
read from the venue, never a row it remembers: the size on screen may be a
fill out of date, and `reduce_only` only caps an order at the position it
finds, it does not grow one to match.

The order goes through `IOrderSubmission.submit`, so every safety gate
applies to it as to any order. It is sent as `OrderPurpose.CLOSE`, so the
app's trading limits pass it: a position larger than the per-order
notional, or a session at its order cap, must still be closable (the PR
#307 review).

**The close must still be the one confirmed** (the PR #307 review). The
user confirms a side and a size; the position is read again before the
order is built, and if it has turned to the other side or grown past the
size shown, `close_mismatch` refuses: closing it would close a position the
user never saw. A position that shrank is still the one confirmed, and the
close is sized from the read.

Plausible extensions, each one function here:
- a partial close (a quantity under the position's size);
- a close at a limit price (`OrderType.LIMIT` and a `time_in_force`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@dataclass(frozen=True)
class ConfirmedClose:
    """The position the user confirmed closing, as its row showed it."""

    symbol: str
    side: PositionSide
    quantity: Decimal


def close_mismatch(confirmed: ConfirmedClose, position: LivePosition) -> str | None:
    """@return Why `position`, read just now, is not the one the user
    confirmed closing, or `None` when it still is."""
    shown = f"{confirmed.side.value.upper()} {confirmed.quantity}"
    now = f"{position.side.value.upper()} {abs(position.position_amt)}"
    if position.side is not confirmed.side:
        return (
            f"The {confirmed.symbol} position turned {now}; it is not the "
            f"{shown} confirmed. Nothing was sent."
        )
    if abs(position.position_amt) > confirmed.quantity:
        return (
            f"The {confirmed.symbol} position grew to {now} from the {shown} "
            "confirmed. Nothing was sent."
        )
    return None


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
        purpose=OrderPurpose.CLOSE,
    )
