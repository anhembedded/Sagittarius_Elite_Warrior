from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class AccountSummaryChangedEvent(BaseEvent):
    """
    @brief A venue's account summary was re-read and differs from the last
    one published (`EPIC-028D`).

    @details Always the whole summary, like `HoldingsChangedEvent`: every
    read is a complete snapshot, so there is no delta to name. The venue is
    the summary's own, exposed as `venue` so a screen's Feed filters this
    event the way it filters every other trading event, with no second
    field that could disagree with the summary.

    Not `frozen`, for the reason `PositionChangedEvent` gives: inheriting
    `BaseEvent` costs it (`EPIC-008F`). Treat as read-only by convention.
    """

    summary: AccountSummary

    @property
    def venue(self) -> TradingVenue:
        return self.summary.venue
