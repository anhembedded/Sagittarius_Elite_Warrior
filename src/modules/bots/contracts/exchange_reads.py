"""`EPIC-047H` — the exchange reads the host publishes besides the facts file: the planner's inputs, the fills and the symbol rules.

@details The VPS tab opens no connection to Binance (decision record 2026-10-27, D1), so what the
Bots tab reads from the exchange for a bot's panel is read by the host and published here, each
with the moment it was read. A reader judges the age by `read_at`; a bot never read has no entry
and the tab says "not published by the host", not an empty value (D5).

@par Why these three
They are the Bots tab's remaining reads (`GetPlannerMarketQuery`, `GetBotFillsQuery` and the
precision of orders and fills over the venue's metadata cache); the exchange facts of a bot are in
the host-facts file (`BotExchangeRead`).

@par Extension cases
  · a funding history or a trades table - one more tuple here with a default, one read in `BotReadRefresh`;
  · another bot kind's inputs - its own field beside `planner`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_fills import BotFills
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class BotPlannerRead:
    """What the planner judges a bot's parameters against, as the host last read it."""

    bot_id: str
    read_at: datetime
    market: PlannerMarket

    def __post_init__(self) -> None:
        if self.read_at.tzinfo is None:
            raise ValueError("an exchange read needs a timezone-aware instant")


@dataclass(frozen=True, slots=True)
class BotFillsRead:
    """A bot's fills, as the host last read the venue's order history."""

    bot_id: str
    read_at: datetime
    fills: BotFills

    def __post_init__(self) -> None:
        if self.read_at.tzinfo is None:
            raise ValueError("an exchange read needs a timezone-aware instant")


@dataclass(frozen=True, slots=True)
class SymbolRulesRead:
    """A bot's symbol's order filters, from the venue's static exchange info (read at start and once a day)."""

    venue: TradingVenue
    symbol: str
    read_at: datetime
    rules: SymbolOrderMetadata

    def __post_init__(self) -> None:
        if self.read_at.tzinfo is None:
            raise ValueError("an exchange read needs a timezone-aware instant")


@dataclass(frozen=True, slots=True)
class HostExchangeReads:
    """Everything the host last read for the tab besides the facts file, at one moment."""

    planner: tuple[BotPlannerRead, ...] = ()
    fills: tuple[BotFillsRead, ...] = ()
    symbol_rules: tuple[SymbolRulesRead, ...] = ()
