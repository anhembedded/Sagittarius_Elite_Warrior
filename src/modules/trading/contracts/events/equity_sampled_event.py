from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class EquitySampledEvent(BaseEvent):
    """
    @brief Domain event fired when a new `EquitySample` is recorded from
    an `ACCOUNT_UPDATE` (`EPIC-021M`).

    @details Not `frozen` — same `BaseEvent` inheritance cost
    `PositionChangedEvent` already documents (a non-frozen base cannot be
    subclassed as frozen). Treat as read-only by convention.
    """

    sample: EquitySample
    #: `EPIC-028C` — the venue this happened on, so a screen showing one
    #: venue never shows another's. No default: a missing venue is exactly
    #: the fill landing in the wrong desk's table.
    venue: TradingVenue = field(kw_only=True)
