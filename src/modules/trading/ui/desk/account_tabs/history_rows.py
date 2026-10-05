"""`EPIC-028J` — one row of the Order history and Trade history tabs, a
display projection of one `OrderRecord` or `TradeRecord`.

@details Mirrors `open_order_row.py`: values, written by the table's formatter
(`EPIC-033N`). A figure the venue did not report is `None` — an empty cell,
never `0`: an order with nothing filled has no average price, and a Spot fill
has no realized PnL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


@dataclass(frozen=True)
class OrderHistoryRow:
    """One past or open order, as values the table writes by kind."""

    symbol: str
    side: OrderSide
    #: The order type as a word, `"STOP MARKET"`.
    order_type: str
    quantity: Decimal
    filled: Decimal
    average_price: Decimal | None
    price: Decimal | None
    stop_price: Decimal | None
    #: The status as a word, `"PARTIALLY FILLED"`.
    status: str
    created: datetime


@dataclass(frozen=True)
class TradeHistoryRow:
    """One fill, as values the table writes by kind."""

    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal
    #: The fee stays in the asset it was charged in (`TradeRecord`), so its
    #: asset is a column of its own: `0.10` USDT and `0.0002` BNB are not one
    #: currency, but a reader still sorts the figures to find the large one.
    fee: Decimal
    fee_asset: str
    realized_pnl: Decimal | None
    time: datetime


def _word(value: str) -> str:
    return value.replace("_", " ").upper()


def build_order_history_row(record: OrderRecord) -> OrderHistoryRow:
    order = record.order
    return OrderHistoryRow(
        symbol=order.symbol,
        side=order.side,
        order_type=_word(order.order_type.value),
        quantity=order.quantity,
        filled=record.executed_quantity,
        average_price=record.average_price,
        price=order.price,
        stop_price=order.stop_price,
        status=_word(order.status.value),
        created=record.created_at,
    )


def build_trade_history_row(record: TradeRecord) -> TradeHistoryRow:
    return TradeHistoryRow(
        symbol=record.symbol,
        side=record.side,
        price=record.price,
        quantity=record.quantity,
        quote_quantity=record.quote_quantity,
        fee=record.fee,
        fee_asset=record.fee_asset,
        realized_pnl=record.realized_pnl,
        time=record.time,
    )
