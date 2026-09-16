"""One row of the Open Orders table — a display projection of one `Order`.

@details Mirrors `position_row.py` next door: every value is formatted here,
in Python, and the table model reads only these strings.

`EPIC-025` PR 1.4b-2 moved this out of `qml/OpenOrdersTable/`; the
`open_order_row_to_qml()` projection went with the QML, for the reason
`position_row.py` records.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_datetime,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import DATETIME_FORMAT


@dataclass(frozen=True)
class OpenOrderRow:
    """One pending order, ready to render. `quantity_text`/`price_text` are
    already formatted strings, same reasoning as `PositionRow`."""

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
