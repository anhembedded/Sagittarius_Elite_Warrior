"""One row of the Open Orders table — a display projection of one `Order`.

@details Mirrors `position_row.py` next door: values, written by the table's
formatter (`EPIC-033N`).

`EPIC-025` PR 1.4b-2 moved this out of `qml/OpenOrdersTable/`; the
`open_order_row_to_qml()` projection went with the QML, for the reason
`position_row.py` records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


@dataclass(frozen=True)
class OpenOrderRow:
    """One pending order, as values the table writes by kind (`EPIC-033N`;
    same reasoning as `PositionRow`)."""

    client_order_id: str
    symbol: str
    side: OrderSide
    #: The order type as a word, `"STOP MARKET"`.
    order_type: str
    quantity: Decimal
    #: `None` for a market order, which has no price of its own.
    price: Decimal | None
    #: The status as a word, `"PARTIALLY FILLED"`.
    status: str
    #: The exchange's own order time (`Order.order_time`); `None` for an
    #: `Order` this app built locally and has not yet had confirmed by the
    #: exchange. The formatter writes it in the display time zone.
    order_time: datetime | None


def _word(value: str) -> str:
    return value.replace("_", " ").upper()


def build_open_order_row(order: Order) -> OpenOrderRow:
    return OpenOrderRow(
        client_order_id=str(order.client_order_id),
        symbol=order.symbol,
        side=order.side,
        order_type=_word(order.order_type.value),
        quantity=order.quantity,
        price=order.price,
        status=_word(order.status.value),
        order_time=order.order_time,
    )
