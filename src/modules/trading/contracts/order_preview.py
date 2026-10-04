"""`EPIC-021E` — the outcome of one `PreviewOrderQuery`: what this app
would send, and whether the exchange's own filters would accept it."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.price_band_check import (
    PriceBandCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)


@dataclass(frozen=True)
class OrderPreview:
    """Immutable result of normalizing one requested order against the
    exchange's rounding/notional rules — never sent anywhere.

    @details `order` already carries the *rounded* quantity/price (see
    `OrderQuantityRoundingPolicy`); `raw_quantity` keeps what the caller
    originally asked for so a formatter can show both, exactly like this
    epic's own worked example ("làm tròn xuống từ 0.0137, step 0.001").
    """

    order: Order
    raw_quantity: Decimal
    estimated_notional: Decimal
    min_notional: Decimal
    step_size: Decimal
    notional_check: NotionalCheck
    #: `EPIC-028O` — for a stop-limit, whether its stop waits for the market
    #: (`stop_trigger_side.py`); `None` for every other order type.
    stop_check: StopPriceCheck | None = None
    #: `BUG-146` — for an order with a price, whether it sits inside the
    #: venue's price band at the request's `last_price`; `None` when the venue
    #: publishes no band, the request carries no last price, or the order has
    #: no price of its own (a market order fills at the market).
    price_band_check: PriceBandCheck | None = None
