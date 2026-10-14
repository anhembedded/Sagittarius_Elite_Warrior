"""`EPIC-039H` — Spot's ladder orders carry no flag: a SELL sells base the bot owns."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_flags import (
    IOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


class SpotOrderFlags(IOrderFlags):
    def reduce_only(self, side: OrderSide) -> bool:
        return False
