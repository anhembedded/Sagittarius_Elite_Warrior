"""`EPIC-028E` — one order as the exchange's order history reports it.

@details Wraps the `Order` the rest of the app already speaks rather than
growing it: `Order` is also the thing this app builds and sends, where "how
much of it filled" and "at what average" have no meaning yet. A history row
adds exactly those two facts and the time the order was created, all read off
the wire (`domain-truth-rule.md`: nothing here is computed from a guess).

On Futures the average price is the exchange's own `avgPrice`; on Spot, which
has no such field, it is `cummulativeQuoteQty / executedQty` — the same
figure Binance's own order history shows. `None` whenever nothing filled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order


@dataclass(frozen=True)
class OrderRecord:
    """An order and how much of it filled, from one history row."""

    order: Order
    executed_quantity: Decimal
    #: `None` when nothing filled — never `0`, which would read as a price.
    average_price: Decimal | None
    #: When the order was created (`time`); `order.order_time` is when it
    #: last changed.
    created_at: datetime
    #: The exchange's own id for the order (`orderId`; `algoId` for a
    #: Futures conditional order), which a `TradeRecord.order_id` names.
    #: `EPIC-029` ADR D6 joins an owner's tagged orders to their fills, and
    #: so to their fees, by it. No default: every constructor reads it off
    #: the wire, and one that forgets fails loudly (`BUG-026`).
    exchange_order_id: int
