"""`BOT-189` — one order of a bot's ladder filled whole.

The typed fact the `ORDER_FILLED` and `CYCLE_COMPLETED` alerts are built on (`PRO-015`): a source
reads this, never the bot's files, and needs no state of its own. `BotOrderFill` is the bot's
inbound copy of one trade report and says nothing of the ladder, so it is not that fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotOrderFilledEvent(BaseEvent):
    """
    @brief Published once per order that executed in full, after the bot has counted the fill
    (never for a partial fill, never for a trade the run already counted).

    @details Kind-neutral: `side` is `BUY` or `SELL` as the order was sent, `price` is the order's
    own price and `quantity` all it executed. `cycle_profit` is set only on the fill that closes a
    grid cycle: the profit that cycle booked, net of both legs' fees; `grid_profit` and
    `completed_cycles` are the run's figures right after the fill. `grid_profit` is the run's profit
    from completed cycles only (`GridRuntime.realised_profit`), not `GridRuntime.realised_total` and
    not the Total PnL (`BOT-202`). `order_id` with `bot_id` names
    the fill, so a consumer can tell a repeat. Published from the bot's worker thread, so a
    consumer marshals itself.

    @par Not `frozen` - the same `BaseEvent` inheritance cost `BotChangedEvent` documents. Treat
    as read-only by convention.
    """

    bot_id: str
    order_id: str
    side: str
    price: Decimal
    quantity: Decimal
    #: The ladder level the order stood at, from the lowest price (0-based, as the bot counts).
    level: int
    grid_profit: Decimal
    completed_cycles: int
    #: The asset the profit figures are in.
    quote_asset: str
    cycle_profit: Decimal | None = None
