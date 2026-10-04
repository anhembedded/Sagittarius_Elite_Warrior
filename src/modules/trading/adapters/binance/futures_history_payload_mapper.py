"""`EPIC-028E` — Futures history rows (`allOrders`, `userTrades`) into
`OrderRecord` and `TradeRecord`.

@details An `allOrders` row is an `openOrders` row plus the fill figures, so
the order itself goes through `map_futures_order_payload_to_order` and only
`executedQty`, `avgPrice` and `time` are read here. Payload shapes are taken
from Binance's documented USD-M API, with the same live-call disclosure as
`futures_account_reader.py`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_payload_mapper import (
    map_futures_order_payload_to_order,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_reads import (
    from_ms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


def map_futures_history_order(payload: dict[str, Any]) -> OrderRecord:
    """@raise KeyError A required field is missing."""
    executed = Decimal(str(payload["executedQty"]))
    average = Decimal(str(payload.get("avgPrice", "0")))
    return OrderRecord(
        order=map_futures_order_payload_to_order(payload),
        executed_quantity=executed,
        average_price=average if executed > 0 and average > 0 else None,
        created_at=from_ms(payload["time"]),
        exchange_order_id=int(payload["orderId"]),
    )


def map_futures_trade(payload: dict[str, Any]) -> TradeRecord:
    """@raise KeyError A required field is missing."""
    return TradeRecord(
        symbol=payload["symbol"],
        trade_id=int(payload["id"]),
        order_id=int(payload["orderId"]),
        side=OrderSide[payload["side"]],
        price=Decimal(str(payload["price"])),
        quantity=Decimal(str(payload["qty"])),
        quote_quantity=Decimal(str(payload["quoteQty"])),
        fee=Decimal(str(payload["commission"])),
        fee_asset=payload["commissionAsset"],
        time=from_ms(payload["time"]),
        realized_pnl=Decimal(str(payload["realizedPnl"])),
    )
