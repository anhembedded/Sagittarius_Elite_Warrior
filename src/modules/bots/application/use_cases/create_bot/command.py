"""`EPIC-029B` — "create a bot from these parameters"."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class CreateBotCommand:
    """A new bot's definition. It is saved as DRAFT; nothing is placed."""

    name: str
    kind: str
    venue: TradingVenue
    symbol: str
    config: Mapping[str, str] = field(default_factory=dict)
