"""`EPIC-029` ADR D15 — where a live chart's candles come from.

@details `LiveChartCoordinator` (`support/charting/live_chart/`) loads a
chart's history and keeps it live. Support imports no module
(`architecture-rule.md` §3), so the candles reach it through this port, which
the owner of the market-data ports implements once
(`market_data/contracts/market_data_candle_feed.py`). Each implementation is
bound to one market: a feed is the market a chart shows.

@par Extension cases (only the market-data feed is built)
  · **A recorded feed** — a backtest replay or a report import draws stored
    candles with no stream: `start_stream` answers a refusal.
  · **An aggregated feed** — a synthetic symbol (a spread, an index) built
    from two feeds.
  · **A cached feed** — a second chart on the same symbol reuses the first
    chart's history.
Each is one new implementation of this ABC; the coordinator does not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame


@dataclass(frozen=True, slots=True)
class CandleStreamStart:
    """Whether a live stream opened, and a line to show the user."""

    success: bool
    message: str


@dataclass(frozen=True, slots=True)
class OlderCandlesRequest:
    """The window to the left of a chart's oldest candle."""

    symbol: str
    interval: TimeFrame
    #: The `open_time` of the oldest candle drawn: the window ends right
    #: before it.
    before: datetime
    #: How many candles at most.
    limit: int


class CandlesUnavailableError(RuntimeError):
    """The exchange will not serve these candles, and asking again will not help
    (`BUG-172`): a timeframe its market has none of (Futures has no `1s`), a
    symbol it does not list (a testnet lists fewer). `reason` is a sentence for
    the user; a screen shows it as it is, never as "try again"."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ICandleFeed(ABC):
    """One market's candles: stored history, a sync from the exchange, and a
    live stream held per owner."""

    @abstractmethod
    def sync(
        self,
        symbol: str,
        interval: TimeFrame,
        cancelled: Callable[[], bool],
        *,
        newest: int | None = None,
    ) -> None:
        """@brief Fetches what is missing from the exchange into the store.
        @param cancelled Polled between fetches; the sync returns early once it
        answers `True`.
        @param newest When given, only the newest `newest` candles are wanted (a
        chart's window), not the implementation's default depth: at `1s` that is
        the difference between 500 candles and millions (`BUG-172`).
        @raise CandlesUnavailableError the exchange refuses these candles for good."""

    @abstractmethod
    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        """@brief The newest `limit` stored candles, **oldest first**: the
        order a chart draws them in."""

    @abstractmethod
    def load_older(
        self, request: OlderCandlesRequest, cancelled: Callable[[], bool]
    ) -> Sequence[MarketData]:
        """@brief Up to `request.limit` candles that open before
        `request.before`, **oldest first** (`BUG-178`): what a chart draws to
        the left of its oldest candle.
        @details The stored candles when the store holds a full window; else
        the exchange's, fetched into the store first, so a chart never draws
        what a restart would not read back. Empty when this market has none
        older. Blocks (it may fetch): a caller runs it off the UI thread.
        @param cancelled Polled between fetches, as `sync` polls it."""

    @abstractmethod
    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        """@brief Makes `symbol` at `interval` this owner's one live stream,
        replacing any it held; another owner's stream is untouched."""

    @abstractmethod
    def stop_stream(self, owner_id: str) -> None:
        """@brief Releases this owner's stream, if it holds one."""
