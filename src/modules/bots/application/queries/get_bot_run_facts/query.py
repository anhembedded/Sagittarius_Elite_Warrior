"""`EPIC-048B` — "what stands in this bot's way that only the host knows"."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class GetBotRunFactsQuery:
    """The bot, with the venue and symbol the screen shows it on."""

    bot_id: str
    venue: TradingVenue
    symbol: str
