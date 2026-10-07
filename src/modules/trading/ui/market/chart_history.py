"""The stored candles a Market chart asks for beyond its first window
(`EPIC-033S`): a chosen range. (The window before the oldest candle drawn is
the shared chart's, `BUG-178`: `ICandleFeed.load_older`.)

Qt-free and thread-free: the chart calls these on a worker thread and draws
the answer on the Qt thread. One market per instance, as a candle feed is
(`MarketDataCandleFeed`): Spot and Futures candles of a symbol are stored
apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)

#: The most candles one Load range… draws: a week of 1m candles is 10,080.
#: A longer range shows its newest candles and says it was cut.
RANGE_CANDLE_LIMIT = 20_000


@dataclass(frozen=True)
class HistoryRange:
    """A span of time in UTC: every candle that opens in it, both ends
    included, as the store reads it."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("a history range is in UTC: both ends need a timezone")
        if self.start >= self.end:
            raise ValueError(f"a history range ends after it starts: {self}")


@dataclass(frozen=True)
class RangeCandles:
    """A range's candles, oldest first; `cut` when the range held more than
    `RANGE_CANDLE_LIMIT` and only the newest were kept."""

    candles: tuple[MarketData, ...]
    cut: bool


class ChartHistory:
    """@brief One market's stored candles, read for a chart."""

    def __init__(self, history: IHistoricalKlines, market: MarketType) -> None:
        self._history = history
        self._market = market

    def in_range(
        self, symbol: str, interval: TimeFrame, span: HistoryRange
    ) -> RangeCandles:
        """Every stored candle that opens in `span`, oldest first, up to
        `RANGE_CANDLE_LIMIT` (the newest ones when there are more)."""
        newest_first = self._history.load(
            self._market,
            symbol,
            interval,
            limit=RANGE_CANDLE_LIMIT + 1,
            start_time=span.start,
            end_time=span.end,
            newest_first=True,
        )
        cut = len(newest_first) > RANGE_CANDLE_LIMIT
        kept = newest_first[:RANGE_CANDLE_LIMIT]
        return RangeCandles(tuple(reversed(kept)), cut)
