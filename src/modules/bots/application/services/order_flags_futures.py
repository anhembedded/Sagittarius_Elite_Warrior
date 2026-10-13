"""`EPIC-039H` — a position venue's ladder flags: the orders that only exit are reduce-only.

@details In one-way mode a counter order exits the position the ladder built, so it is sent
reduce-only (decision O10): a LONG grid's SELLs, a SHORT grid's BUYs. A NEUTRAL grid's orders can
open on either side and are not. Post-only is not used (O10).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_flags import (
    IOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


class PositionOrderFlags(IOrderFlags):
    def __init__(self, direction: TradeDirection) -> None:
        self._direction = direction

    def reduce_only(self, side: OrderSide) -> bool:
        if self._direction is TradeDirection.LONG:
            return side is OrderSide.SELL
        if self._direction is TradeDirection.SHORT:
            return side is OrderSide.BUY
        return False
