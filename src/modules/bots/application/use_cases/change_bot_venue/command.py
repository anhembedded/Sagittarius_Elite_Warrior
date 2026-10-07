"""`BOT-171` — "put this draft bot on another Spot venue"."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class ChangeBotVenueCommand:
    """The bot and the Spot venue it moves to. Only a DRAFT that never ran may
    move; no confirmation is asked here, the real-money one runs at Start."""

    bot_id: str
    venue: TradingVenue
