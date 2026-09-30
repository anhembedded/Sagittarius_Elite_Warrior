"""`EPIC-028H` — what the confirmation dialog tells the user before an order
is sent (HLD 11 §11.5: a money-moving action confirms in a dialog that names
the consequence).

@details Built from the exchange-rounded `OrderPreview`, not from what was
typed, so the dialog shows the quantity and price that will actually be sent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_estimates import (
    estimated_fee,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.amount_text import (
    format_amount,
)


@dataclass(frozen=True)
class OrderConfirmation:
    """The question the dialog asks, and the lines that explain it."""

    title: str
    question: str
    details: str


#: Asks the user; `True` sends the order. Injected so a test answers without
#: a modal dialog waiting for a click (`open_orders_panel.py`'s
#: `ConfirmCancel` established the shape).
type ConfirmOrder = Callable[[OrderConfirmation], bool]


def build_confirmation(
    preview: OrderPreview,
    *,
    side_label: str,
    venue_label: str,
    base_asset: str,
    quote_asset: str,
    price: Decimal,
    fee_rate: Decimal,
) -> OrderConfirmation:
    """@param price The rounded limit price, or for a market order the last
    price the estimate used."""
    order = preview.order
    is_market = order.order_type is OrderType.MARKET
    kind = "market" if is_market else "limit"
    about = "about " if is_market else ""
    total = order.quantity * price
    fee = estimated_fee(order.quantity, price, fee_rate)
    lines = [
        f"Total: {about}{format_amount(total)} {quote_asset}",
        f"Estimated fee: {format_amount(fee)} {quote_asset}",
    ]
    if preview.raw_quantity != order.quantity:
        lines.append(
            f"The amount was rounded down from {format_amount(preview.raw_quantity)} "
            f"to the lot step of {format_amount(preview.step_size)}."
        )
    lines.append("The order is sent to the exchange at once.")
    return OrderConfirmation(
        title=f"Place {side_label} order",
        question=(
            f"{side_label} {format_amount(order.quantity)} {base_asset} at "
            f"{about}{format_amount(price)} {quote_asset}, as a {kind} order on "
            f"{venue_label}?"
        ),
        details="\n".join(lines),
    )
