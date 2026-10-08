"""`EPIC-035L` — a running Grid's price left its range, or came back.

The typed fact the range-exit alert is built on (`EPIC-036B`'s `RANGE_EXIT`): a
source reads `position`, never the bot's state, and needs no timer of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotRangeChangedEvent(BaseEvent):
    """
    @brief Published when a running Grid's price changes its place against the
    range: it left (`BELOW` or `ABOVE`) or came back (`INSIDE`).

    @details Once per change, never per tick: a price that stays outside is one
    event, and the return re-arms the next exit. `price` is the tick's last price
    (the close), the same `PriceTick` the stop loss reads (`BUG-191`). A bot's
    behaviour does not change with it (owner decision D2): there is no automatic
    exit. Published from the bot's worker thread, so a consumer marshals itself.

    @par Not `frozen` — the same `BaseEvent` inheritance cost `BotChangedEvent`
    documents. Treat as read-only by convention.
    """

    bot_id: str
    symbol: str
    position: RangePosition
    price: Decimal
    lower: Decimal
    upper: Decimal
