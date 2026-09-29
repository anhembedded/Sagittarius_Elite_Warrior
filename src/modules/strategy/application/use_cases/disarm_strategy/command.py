"""`EPIC-022B` — "stop running any strategy"."""

from __future__ import annotations

from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class DisarmStrategyCommand:
    """@brief Command to clear the live strategy (`EPIC-022A`) of one venue.

    @details Only the venue (`EPIC-028B`): each venue has at most one armed
    strategy (`BUG-085`), so the venue identifies it.
    """

    venue: TradingVenue = field(kw_only=True)
