from dataclasses import dataclass, field
from datetime import datetime

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetTradeHistoryQuery:
    """@brief Query for one page of a venue's trade history, newest first
    (`EPIC-028E`, ADR O5: the desk asks for the last seven days, fifty rows a
    page)."""

    venue: TradingVenue = field(kw_only=True)
    #: One symbol, or `None` for every symbol the venue names as active.
    symbol: str | None = field(kw_only=True)
    #: The oldest moment to include; timezone-aware, so it is one instant
    #: whatever the machine's local zone.
    since: datetime = field(kw_only=True)
    #: Zero-based.
    page: int = field(default=0, kw_only=True)
    #: The desk's own pair, read after the pairs with an open order when an
    #: every-pair page is capped (`BOT-149`).
    desk_symbol: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if self.since.tzinfo is None:
            raise ValueError("since must be timezone-aware")
        if self.page < 0:
            raise ValueError(f"page must be zero or more, got {self.page}")
