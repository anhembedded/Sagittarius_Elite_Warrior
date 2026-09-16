"""`EPIC-024B` §2 — the exact translation this task's own mapping table
exists to lock: a human's Long/Short button click, plus the real current
position, into the Binance side/`reduceOnly` pair a live order actually
needs.

@details `domain-truth-rule.md` forbids collapsing this: "Long"/"Short" on
the manual trading form is a *position direction*, not `OrderSide` — the
same subtlety `signal_action_to_order_intent.py` already names for the
strategy path. One-way mode means Binance has no "SHORT" order side either
way; `OrderSide.SELL` both closes a LONG and opens a SHORT, and only
`reduceOnly` tells them apart. Unlike the strategy path, the caller here
must always pass the *real*, freshly-read current position
(`ITradingClient.get_positions()` — never guessed, never remembered from a
prior click) — a human can click Long/Short in either order, at any time,
with no signal history to fall back on the way `LiveTradingCoordinator`
does.
"""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_intent import (
    OrderIntent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


class ManualOrderDirection(str, Enum):
    """@brief The two buttons the manual trading form ever shows — a
    position direction, never an `OrderSide` (see this module's own
    docstring)."""

    LONG = "LONG"
    SHORT = "SHORT"


_ORDER_SIDE_BY_DIRECTION: dict[ManualOrderDirection, OrderSide] = {
    ManualOrderDirection.LONG: OrderSide.BUY,
    ManualOrderDirection.SHORT: OrderSide.SELL,
}

#: The position side a click is closing/reducing, not opening — `EPIC-024B`
#: §2's table: Long closes an existing Short, Short closes an existing Long.
_OPPOSITE_POSITION_SIDE: dict[ManualOrderDirection, PositionSide] = {
    ManualOrderDirection.LONG: PositionSide.SHORT,
    ManualOrderDirection.SHORT: PositionSide.LONG,
}


def manual_order_intent_for(
    direction: ManualOrderDirection, current_position: LivePosition | None
) -> OrderIntent:
    """@brief `EPIC-024B` §2's 4-row table, as code.
    @param current_position The account's real, just-read position on the
    target symbol — `None` when flat. Never inferred from `direction` or
    from a prior call; a flat position is absent from `ITradingClient.
    get_positions()`'s result (see `LivePosition`'s own docstring), not a
    zero-amount entry, so `None` is the only way "flat" is represented.
    """
    side = _ORDER_SIDE_BY_DIRECTION[direction]
    reduce_only = (
        current_position is not None
        and current_position.side is _OPPOSITE_POSITION_SIDE[direction]
    )
    return OrderIntent(side=side, reduce_only=reduce_only)
