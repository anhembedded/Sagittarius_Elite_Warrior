"""`EPIC-034D` — "can this bot's venue be connected to, for this symbol"."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class GetVenueConnectionQuery:
    """The venue and symbol a bot is connecting to."""

    venue: TradingVenue
    symbol: str
