"""`EPIC-028H` — what the confirmation dialog tells the user before an order
is sent (HLD 11 §11.5: a money-moving action confirms in a dialog that names
the consequence).

@details Built from the exchange-rounded `OrderPreview`, not from what was
typed, so the dialog shows the quantity and price that will actually be sent.
`EPIC-028O`: a stop-limit names its stop, and a market buy sized by quote
names what it spends rather than an amount the exchange will decide.
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
    if order.quote_quantity is not None:
        return _quote_buy_confirmation(
            preview, side_label, venue_label, base_asset, quote_asset, fee_rate
        )
    is_market = order.order_type is OrderType.MARKET
    kind = _KIND.get(order.order_type, "limit")
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
    trigger = ""
    if order.stop_price is not None:
        stop = f"{format_amount(order.stop_price)} {quote_asset}"
        trigger = f" once the price reaches {stop}"
        lines.append(f"It joins the book only when the last price reaches {stop}.")
    return OrderConfirmation(
        title=f"Place {side_label} order",
        question=(
            f"{side_label} {format_amount(order.quantity)} {base_asset} at "
            f"{about}{format_amount(price)} {quote_asset}{trigger}, as a {kind} "
            f"order on {venue_label}?"
        ),
        details="\n".join(lines),
    )


_KIND = {
    OrderType.MARKET: "market",
    OrderType.LIMIT: "limit",
    OrderType.STOP_LIMIT: "stop-limit",
}


def _quote_buy_confirmation(
    preview: OrderPreview,
    side_label: str,
    venue_label: str,
    base_asset: str,
    quote_asset: str,
    fee_rate: Decimal,
) -> OrderConfirmation:
    """`EPIC-028O` — a market buy sized by the quote it spends: the spend is
    exact, the amount bought is the exchange's to decide."""
    order = preview.order
    spend = order.quote_quantity or Decimal(0)
    lines = [
        f"Spend: {format_amount(spend)} {quote_asset}",
        f"Estimated amount: about {format_amount(order.quantity)} {base_asset}",
        f"Estimated fee: {format_amount(spend * fee_rate)} {quote_asset}",
        "The order is sent to the exchange at once.",
    ]
    return OrderConfirmation(
        title=f"Place {side_label} order",
        question=(
            f"Spend {format_amount(spend)} {quote_asset} to {side_label.lower()} "
            f"{base_asset}, as a market order on {venue_label}?"
        ),
        details="\n".join(lines),
    )
