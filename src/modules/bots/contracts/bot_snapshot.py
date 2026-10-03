"""`EPIC-029B` — the read model the Bots tab lists (`EPIC-029F`).

Flat and frozen, built from a `Bot` by the queries; a screen never holds the
aggregate itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class BotSnapshot:
    """One bot as a list row or a detail panel shows it."""

    bot_id: str
    name: str
    kind: str
    venue: TradingVenue
    symbol: str
    state: BotLifecycleState
    created_at: datetime
    run_started_at: datetime | None
    config: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))

    @classmethod
    def of(cls, bot: Bot) -> BotSnapshot:
        definition = bot.definition
        return cls(
            bot_id=bot.bot_id.value,
            name=definition.name,
            kind=definition.kind,
            venue=definition.venue,
            symbol=definition.symbol,
            state=bot.state,
            created_at=bot.created_at,
            run_started_at=bot.lifecycle.run_started_at,
            config=definition.config,
        )
