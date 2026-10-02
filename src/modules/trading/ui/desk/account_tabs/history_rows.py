"""`EPIC-028J` — one row of the Order history and Trade history tabs, a
display projection of one `OrderRecord` or `TradeRecord`.

@details Mirrors `open_order_row.py`: every value is formatted here, and the
table models read only these strings. A figure the venue did not report is
"—", never `0`: an order with nothing filled has no average price, and a
Spot fill has no realized PnL.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import DATETIME_FORMAT
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_datetime,
)

_NONE = "—"


@dataclass(frozen=True)
class OrderHistoryRow:
    """One past or open order, ready to render."""

    symbol: str
    side: OrderSide
    order_type_text: str
    quantity_text: str
    filled_text: str
    average_price_text: str
    price_text: str
    stop_price_text: str
    status_text: str
    created_text: str


@dataclass(frozen=True)
class TradeHistoryRow:
    """One fill, ready to render."""

    symbol: str
    side: OrderSide
    price_text: str
    quantity_text: str
    quote_quantity_text: str
    fee_text: str
    realized_pnl_text: str
    time_text: str


def build_order_history_row(
    record: OrderRecord, tz_name: str = DEFAULT_TIMEZONE
) -> OrderHistoryRow:
    order = record.order
    return OrderHistoryRow(
        symbol=order.symbol,
        side=order.side,
        order_type_text=order.order_type.value.replace("_", " ").upper(),
        quantity_text=f"{order.quantity:,.4f}",
        filled_text=f"{record.executed_quantity:,.4f}",
        average_price_text=_price_or_none(record.average_price),
        price_text=_price_or_none(order.price),
        stop_price_text=_price_or_none(order.stop_price),
        status_text=order.status.value.replace("_", " ").upper(),
        created_text=format_display_datetime(
            record.created_at, tz_name=tz_name, fmt=DATETIME_FORMAT
        ),
    )


def build_trade_history_row(
    record: TradeRecord, tz_name: str = DEFAULT_TIMEZONE
) -> TradeHistoryRow:
    return TradeHistoryRow(
        symbol=record.symbol,
        side=record.side,
        price_text=f"{record.price:,.2f}",
        quantity_text=f"{record.quantity:,.4f}",
        quote_quantity_text=f"{record.quote_quantity:,.2f}",
        # The fee stays in the asset it was charged in (`TradeRecord`).
        fee_text=f"{record.fee:,.8f} {record.fee_asset}",
        realized_pnl_text=(
            f"{record.realized_pnl:+,.2f}" if record.realized_pnl is not None else _NONE
        ),
        time_text=format_display_datetime(
            record.time, tz_name=tz_name, fmt=DATETIME_FORMAT
        ),
    )


def _price_or_none(price: Decimal | None) -> str:
    return f"{price:,.2f}" if price is not None else _NONE
