from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class PositionClosedEvent(BaseEvent):
    """
    @brief Domain event fired when `symbol`'s open position closes to flat
    (`BUG-086`).

    @details A dedicated event, not `PositionChangedEvent` with a
    fabricated `position_amt=0` `LivePosition` — that VO's own docstring
    states the invariant directly: "Zero never appears here — a flat
    position is simply absent ..., not a `LivePosition` with
    `position_amt == 0`". There is nothing to snapshot once a position is
    gone, so this event carries only the one fact a consumer needs: which
    symbol to remove.

    @par Not `frozen` — same `BaseEvent` inheritance cost `PositionChangedEvent`
    already documents. Treat as read-only by convention.
    """

    symbol: str
    #: `EPIC-028C` — the venue this happened on, so a screen showing one
    #: venue never shows another's. No default: a missing venue is exactly
    #: the fill landing in the wrong desk's table.
    venue: TradingVenue = field(kw_only=True)
