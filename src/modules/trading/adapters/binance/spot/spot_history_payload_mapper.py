"""`EPIC-028E` — Spot history rows (`allOrders`, `myTrades`) into
`OrderRecord` and `TradeRecord`.

@details Two differences from Futures, both from Binance's documented Spot
API: an order row has no `avgPrice`, so the average is
`cummulativeQuoteQty / executedQty` (the figure Binance's own order history
shows); a trade row has no `side`, only `isBuyer`. A negative
`cummulativeQuoteQty` is Binance's marker for "not available" (very old
orders), so it gives no average rather than a negative one (`EPIC-028Q`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_reads import (
    from_ms,
    order_on_machine_clock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_order_payload_mapper import (
    map_spot_order_payload_to_order,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


def map_spot_history_order(
    payload: dict[str, Any], clock_offset_ms: int = 0
) -> OrderRecord:
    """@param clock_offset_ms The exchange's clock less the machine's: the
    record's time is on the machine's (`BUG-189`).
    @raise KeyError A required field is missing."""
    executed = Decimal(str(payload["executedQty"]))
    quote = Decimal(str(payload["cummulativeQuoteQty"]))
    return OrderRecord(
        order=order_on_machine_clock(
            map_spot_order_payload_to_order(payload), clock_offset_ms
        ),
        executed_quantity=executed,
        average_price=quote / executed if executed > 0 and quote >= 0 else None,
        created_at=from_ms(payload["time"], clock_offset_ms),
        exchange_order_id=int(payload["orderId"]),
    )


def map_spot_trade(payload: dict[str, Any], clock_offset_ms: int = 0) -> TradeRecord:
    """@param clock_offset_ms As for `map_spot_history_order`.
    @raise KeyError A required field is missing."""
    return TradeRecord(
        symbol=payload["symbol"],
        trade_id=int(payload["id"]),
        order_id=int(payload["orderId"]),
        side=OrderSide.BUY if payload["isBuyer"] else OrderSide.SELL,
        price=Decimal(str(payload["price"])),
        quantity=Decimal(str(payload["qty"])),
        quote_quantity=Decimal(str(payload["quoteQty"])),
        fee=Decimal(str(payload["commission"])),
        fee_asset=payload["commissionAsset"],
        time=from_ms(payload["time"], clock_offset_ms),
    )
