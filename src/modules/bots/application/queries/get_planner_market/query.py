"""`EPIC-029F` — "what the planner needs to judge a bot on this symbol"."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class GetPlannerMarketQuery:
    """The venue and symbol a bot is being planned for."""

    venue: TradingVenue
    symbol: str
