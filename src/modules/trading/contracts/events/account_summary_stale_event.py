from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class AccountSummaryStaleEvent(BaseEvent):
    """
    @brief A venue's account could not be re-read, so the summary last
    published for it is out of date (`EPIC-028Q`).

    @details Published once when reads start failing, not on every failed
    tick; the next `AccountSummaryChangedEvent` for the venue ends it, and is
    published even when the summary read back is unchanged. Without it a
    desk kept showing the last balance as current while every read failed
    (the PR #300 epic review, §3 item 6). `reason` is the sentence a desk
    shows next to the stale figures.

    Not `frozen`, for the reason `PositionChangedEvent` gives: inheriting
    `BaseEvent` costs it (`EPIC-008F`). Treat as read-only by convention.
    """

    reason: str
    #: No default, like every trading event since `EPIC-028C`: a missing
    #: venue is a stale marker on the wrong desk.
    venue: TradingVenue = field(kw_only=True)
