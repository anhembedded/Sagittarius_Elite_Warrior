from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide


@dataclass(frozen=True)
class PreviewOrderQuery:
    """@brief Query to build and validate one live order without sending it
    (`EPIC-021E`).

    @details `reference_price` is required and caller-supplied — this app
    has no live mark-price network path in scope for this task (fetching
    one belongs to `EPIC-021F`'s real execution path, not this
    domain-and-preview task); the caller decides what price the notional
    estimate is computed against. For `OrderType.LIMIT` this doubles as the
    order's own limit price; for the other order types it is only used to
    estimate notional.
    """

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    reference_price: Decimal
