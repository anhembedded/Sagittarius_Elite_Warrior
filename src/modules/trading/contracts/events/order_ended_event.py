from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class OrderEndedEvent(BaseEvent):
    """
    @brief Domain event fired when `order` is over without having filled
    whole: cancelled, rejected or expired (`ended_without_filling`).

    @details `EPIC-028I` (the PR #307 review): `OrderFilledEvent` fires only
    for a trade, so an entry cancelled before or after a partial fill was
    otherwise never reported, and the desk waiting to protect it waited for
    ever. `order.status` says how it ended; whatever filled before that was
    reported by its own `OrderFilledEvent`s.

    @par Not `frozen` — same `BaseEvent` inheritance cost `OrderFilledEvent`
    already documents. Treat as read-only by convention.
    """

    order: Order
    #: The venue this happened on, so a screen showing one venue never
    #: shows another's. No default, as on every account event (`EPIC-028C`).
    venue: TradingVenue = field(kw_only=True)
