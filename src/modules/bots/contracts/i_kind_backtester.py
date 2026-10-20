"""`EPIC-040B` — the seam every kind's backtest plugs into (ADR D2, architecture rule §7.2.1).

A kind that can be replayed over stored candles supplies one `IKindBacktester`: it takes the
parameters, the terms they are judged against and a period, and answers with a kind-neutral
`BacktestAnswer` (an outcome, a refusal in words, or a cancellation). The workbench (`EPIC-040D`)
draws any kind's outcome without naming the kind; a kind reaches it through `IBotKind.backtester()`,
so the kind catalog finds it by kind id.

@par Extension cases (only the Grid is built: `GridKindBacktester`)
  · **Strategy bot** (`EPIC-040G`): reads `request.warmup` to prime its indicators before `start`
    and reports entries and exits as fills; calls the same `IStrategyEngine` as the live bot.
  · **DCA** (`EPIC-029L`): scheduled buys as fills, its safety-order figures as `BacktestFigure`s.
  · **A kind that needs no history before the period** (the Grid): ignores `warmup`.
Each is one class implementing this ABC and one `backtester()` override; the workbench and the
request do not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
)
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
class KindBacktestRequest:
    """The parameters, the terms they are judged against and the period (`EPIC-040B`).

    `terms` are the symbol's filters and fees (`GetPlannerMarketQuery`), never the account's
    balance: a replay is judged by the symbol's rules only (`EPIC-040C`). `venue` is the bot's:
    the candles replayed are those stored from the market its orders fill in (`BUG-172`).
    `warmup` is the history before `start` a kind may want replayed to prime itself; nothing is
    reported before `start`. `cancelled` is asked before every candle (`async-ui-action-rule.md`).
    `brackets` and `funding` are read only for a venue that holds a position (`EPIC-039K`)."""

    symbol: str
    config: Mapping[str, str]
    terms: ExchangeTerms
    interval: TimeFrame
    start: datetime
    end: datetime
    venue: TradingVenue
    warmup: timedelta = timedelta(0)
    cancelled: Callable[[], bool] = _never
    brackets: LeverageBrackets | None = None
    funding: FundingRequirement = field(default=FundingRequirement.REQUIRED)

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("a backtest period must end after it starts")
        if self.warmup < timedelta(0):
            raise ValueError("a backtest's warm-up cannot be negative")
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))


class IKindBacktester(ABC):
    """One kind's replay of its parameters over stored candles."""

    @abstractmethod
    def run(self, request: KindBacktestRequest) -> BacktestAnswer:
        """Replays `request` and answers; never raises for a period that cannot be replayed (a
        refusal says why), and answers `BacktestCancelled`, never a partial outcome, when
        `request.cancelled` turns true."""
