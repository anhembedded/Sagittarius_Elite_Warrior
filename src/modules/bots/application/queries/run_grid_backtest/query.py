"""`EPIC-029D` — "replay these Grid parameters over this period"."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _never() -> bool:
    return False


@dataclass(frozen=True, slots=True)
class RunGridBacktestQuery:
    """The parameters on screen, the terms they are judged against, the period.

    `terms` are the planner's (`GetPlannerMarketQuery`): the venue's filters
    and the account's fees, so a replay charges what a live run would.
    `venue` is the bot's: the candles replayed are the ones stored from the market
    its orders fill in, never another venue's (`BUG-172`).
    `cancelled` is asked before every candle (`async-ui-action-rule.md`).
    `brackets` and `funding` are read only for a venue that holds a position (`EPIC-039K`)."""

    symbol: str
    config: Mapping[str, str]
    terms: ExchangeTerms
    interval: TimeFrame
    start: datetime
    end: datetime
    venue: TradingVenue
    cancelled: Callable[[], bool] = _never
    #: `EPIC-039K` - the symbol's leverage brackets, which a position venue's liquidation
    #: price needs. Read by the caller (`GetLeverageBracketsQuery`); a Futures backtest
    #: without them is refused, never replayed with a guessed table.
    brackets: LeverageBrackets | None = None
    #: What a Futures backtest does when the funding history cannot be read.
    funding: FundingRequirement = FundingRequirement.REQUIRED

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("a backtest period must end after it starts")
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))
