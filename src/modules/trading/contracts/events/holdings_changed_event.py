from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class HoldingsChangedEvent(BaseEvent):
    """
    @brief Domain event fired when the account's Spot holdings are re-read
    (`EPIC-027O`).

    @details Always the complete set, unlike `PositionChangedEvent`/
    `PositionClosedEvent`'s per-symbol pair: positions also arrive
    incrementally from the Futures user-data stream's `ACCOUNT_UPDATE`
    deltas, so a changed/closed distinction earns its keep there. Holdings
    have no such incremental side-channel in this app — every holdings read
    `HoldingsRefreshService` publishes is already the whole account
    snapshot, so a `HoldingClosedEvent` would be structure with no real
    delta behind it.

    Not `frozen`, for the same reason `PositionChangedEvent` gives:
    inheriting `BaseEvent` costs it (`EPIC-008F`). Treat as read-only by
    convention.
    """

    holdings: tuple[SpotHolding, ...]
    #: `EPIC-028C` — the venue this happened on, so a screen showing one
    #: venue never shows another's. No default: a missing venue is exactly
    #: the fill landing in the wrong desk's table.
    venue: TradingVenue = field(kw_only=True)
