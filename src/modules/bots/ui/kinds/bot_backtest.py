"""`EPIC-029D` — a kind's backtest, as the Bots screen hosts it.

The seam: the screen asks `kind_panels.backtest_for(kind_id)` and gets a
`BotBacktest` or nothing, then shows its page in the detail panel's Backtest
tab and tells it what is selected. The screen never names a kind.

This page-per-kind seam is being replaced (`EPIC-040D` built the kind-neutral workbench, `EPIC-040F`
retires this page for the Grid): a new kind no longer writes a page. The recipes are now:
· a kind's backtest — its `IKindBacktester`, returned by `IBotKind.backtester()`, answering a
  `BacktestOutcome` (`contracts/i_kind_backtester.py`); the workbench draws it;
· a kind's parameter editor — one `BotKindPanel` entry in `kind_panels`;
· a kind with no backtest — `IBotKind.backtester()` answers `None`, and the workbench refuses it in
  words.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    BOT_MARKET,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@dataclass(frozen=True, slots=True)
class BacktestContext:
    """What is selected, as a backtest needs it."""

    bot_id: str
    #: The bot's venue: the market the replay reads is the one its orders fill in.
    venue: TradingVenue
    symbol: str
    #: The parameters on screen: the user's edits when there are any.
    config: Mapping[str, str]
    #: The planner's terms (filters and fees); `None` until they are read.
    terms: ExchangeTerms | None
    #: A position venue's leverage brackets, read for the plan's liquidation (`EPIC-039J`);
    #: `None` until read, and always `None` on Spot.
    brackets: LeverageBrackets | None = None


@dataclass(frozen=True)
class BacktestPorts:
    """What every kind's backtest is built from, for one venue (`BUG-172`):
    the sync and the result chart read that venue's market."""

    thread_manager: IThreadManager
    dispatcher: ICommandDispatcher
    sync: IMarketDataSync
    #: The venue's Spot candle feed the result chart is built on (it only draws).
    feed: ICandleFeed
    #: How a backtest that could not run reaches the user (`BOT-169`).
    notifier: INotifier
    #: The market the venue's candles are read in (`EPIC-039J`): the result chart's.
    market: MarketType = BOT_MARKET


class BotBacktest(ABC):
    """@brief One kind's backtest: a page, told what is selected."""

    @property
    @abstractmethod
    def page(self) -> QWidget:
        """The widget the Backtest tab shows."""

    @abstractmethod
    def follow(self, context: BacktestContext | None) -> None:
        """What is selected now; `None` for nothing. A different bot cancels
        a run in flight and clears the last result."""

    @abstractmethod
    def shutdown(self) -> None:
        """Cancels a run in flight; nothing it computes is shown."""
