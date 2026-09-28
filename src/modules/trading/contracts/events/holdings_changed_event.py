from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
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
