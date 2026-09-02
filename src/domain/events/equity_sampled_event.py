from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample
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
