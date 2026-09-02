"""Row projection for `OpenOrdersTable.qml` (`EPIC-021I`).

@details Mirrors `PositionsTable/positions_row.py`'s split: formatting
happens here, in Python, so the `.qml` stays a dumb renderer of
pre-formatted dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import DATETIME_FORMAT
from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_datetime,
)


@dataclass(frozen=True)
class OpenOrderRow:
    """One row of the Open Orders table — a display projection of one
    `Order`. `quantity_text`/`price_text` are already formatted strings,
    same reasoning as `PositionRow`."""

    client_order_id: str
    symbol: str
    side: OrderSide
    order_type_text: str
    quantity_text: str
    price_text: str
    status_text: str
    #: The exchange's own order time (`Order.order_time`), rendered in the
    #: user's display timezone — same source `TradeLogRow`'s own
    #: `entryTimeText`/`exitTimeText` reads. "—" for an `Order` this app
    #: built locally and has not yet had confirmed by the exchange.
    order_time_text: str


def build_open_order_row(order: Order, tz_name: str = DEFAULT_TIMEZONE) -> OpenOrderRow:
    return OpenOrderRow(
        client_order_id=str(order.client_order_id),
        symbol=order.symbol,
        side=order.side,
        order_type_text=order.order_type.value.replace("_", " ").upper(),
        quantity_text=f"{order.quantity:,.4f}",
        price_text=f"{order.price:,.2f}" if order.price is not None else "—",
        status_text=order.status.value.replace("_", " ").upper(),
        order_time_text=(
            format_display_datetime(
                order.order_time, tz_name=tz_name, fmt=DATETIME_FORMAT
            )
            if order.order_time is not None
            else "—"
        ),
    )


def open_order_row_to_qml(row: OpenOrderRow) -> dict[str, Any]:
    return {
        "clientOrderId": row.client_order_id,
        "symbol": row.symbol,
        "sideLabel": row.side.value.upper(),
        "sideIsBuy": row.side is OrderSide.BUY,
        "orderTypeText": row.order_type_text,
        "quantityText": row.quantity_text,
        "priceText": row.price_text,
        "statusText": row.status_text,
        "orderTimeText": row.order_time_text,
    }


def open_order_rows_to_qml(rows: list[OpenOrderRow]) -> list[dict[str, Any]]:
    return [open_order_row_to_qml(row) for row in rows]
