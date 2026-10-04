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

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame


@dataclass(frozen=True, slots=True)
class CandleStreamStart:
    """Whether a live stream opened, and a line to show the user."""

    success: bool
    message: str


class ICandleFeed(ABC):
    """One market's candles: stored history, a sync from the exchange, and a
    live stream held per owner."""

    @abstractmethod
    def sync(
        self, symbol: str, interval: TimeFrame, cancelled: Callable[[], bool]
    ) -> None:
        """@brief Fetches what is missing from the exchange into the store.
        @param cancelled Polled between fetches; the sync returns early once it
        answers `True`."""

    @abstractmethod
    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        """@brief The newest `limit` stored candles, **oldest first**: the
        order a chart draws them in."""

    @abstractmethod
    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        """@brief Makes `symbol` at `interval` this owner's one live stream,
        replacing any it held; another owner's stream is untouched."""

    @abstractmethod
    def stop_stream(self, owner_id: str) -> None:
        """@brief Releases this owner's stream, if it holds one."""
