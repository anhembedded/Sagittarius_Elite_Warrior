"""`EPIC-021E` — the outcome of one `PreviewOrderQuery`: what this app
would send, and whether the exchange's own filters would accept it."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order


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
