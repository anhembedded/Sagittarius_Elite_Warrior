"""`EPIC-028E` — Spot history rows (`allOrders`, `myTrades`) into
`OrderRecord` and `TradeRecord`.

@details Two differences from Futures, both from Binance's documented Spot
API: an order row has no `avgPrice`, so the average is
`cummulativeQuoteQty / executedQty` (the figure Binance's own order history
shows); a trade row has no `side`, only `isBuyer`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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


def _time(raw_ms: Any) -> datetime:
    return datetime.fromtimestamp(int(raw_ms) / 1000, tz=UTC)


def map_spot_history_order(payload: dict[str, Any]) -> OrderRecord:
    """@raise KeyError A required field is missing."""
    executed = Decimal(str(payload["executedQty"]))
    quote = Decimal(str(payload["cummulativeQuoteQty"]))
    return OrderRecord(
        order=map_spot_order_payload_to_order(payload),
        executed_quantity=executed,
        average_price=quote / executed if executed > 0 else None,
        created_at=_time(payload["time"]),
    )


def map_spot_trade(payload: dict[str, Any]) -> TradeRecord:
    """@raise KeyError A required field is missing."""
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
        time=_time(payload["time"]),
    )
