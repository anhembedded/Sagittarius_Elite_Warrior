"""The verified fake for `IHistoricalKlines` (HLD §10.3).

**Who needs it.** Six call sites read stored candles, and `IHistoricalKlines`
is a *foreign* port to every one of them, so `Mock(spec=IHistoricalKlines)` is
not an option — `test_no_foreign_port_is_mocked.py` fails on it, because a mock
agrees with whatever the test asserts and cannot notice the day the port's real
behaviour changes.

**Why this is a second implementation and not the real one over a fake store.**
Composing `GetHistoricalKlinesQueryHandler` with `FakeMarketDataRepository`
would give a fake that cannot diverge, which is tempting — but it would make
`contracts/` depend on `application/`, and this file would be the first in the
module to invert that direction. The epic has not settled whether a module's
published package may reach inward, and a fake is a poor place to decide it.
So the established mechanism does the work instead: the contract suite next
door runs against **both** this class and the real handler (composed in the
test file, where importing `application/` costs nothing), and any divergence
fails a test rather than hiding.

**Bounds are inclusive on both ends, and `limit` applies after ordering** —
both copied deliberately from `FakeMarketDataRepository._rows`, which copied
them from the real `get_klines()`. Getting either wrong here would make this
fake lie in the one direction the contract suite is built to catch.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    DEFAULT_KLINE_LIMIT,
    IHistoricalKlines,
)


def _interval_value(interval: TimeFrame | str) -> str:
    """`TimeFrame` is a `str` `Enum`, so a caller may hand over either. Keyed
    by the value so `TimeFrame.ONE_MINUTE` and `"1m"` name one series — the
    same normalisation `FakeMarketDataRepository` performs, for the same
    reason."""
    return interval.value if isinstance(interval, TimeFrame) else str(interval)


@dataclass(frozen=True, slots=True)
class KlineRead:
    """One `load`/`load_many` call, as the caller made it.

    A record rather than a tuple because consumers assert on five of its six
    fields — "the chart asked for 500 candles, newest first, bounded by the
    picked date range" is a fact about the *screen*, and reading it off
    `read.limit` beats unpacking a six-tuple at every call site.
    """

    #: One entry for `load()`, every symbol asked for `load_many()`.
    symbols: tuple[str, ...]
    interval: TimeFrame
    limit: int
    start_time: datetime | None
    end_time: datetime | None
    newest_first: bool


class FakeHistoricalKlines(IHistoricalKlines):
    """Stored candles a test controls, read through the port's promises."""

    def __init__(self) -> None:
        self._series: dict[tuple[str, str], dict[datetime, MarketData]] = {}
        #: Every `load`/`load_many` call, in order. A consumer's test often
        #: needs "the chart asked for 500 candles, not 5000", or "the date
        #: range reached the read" — facts about the screen, not the store.
        self.reads: list[KlineRead] = []

    def seed(self, klines: Sequence[MarketData]) -> None:
        """Put rows in the store, as a completed sync would have.

        Upsert on `open_time`, like the real primary key: the same candle
        seeded twice replaces rather than duplicates, so a test that seeds
        overlapping windows gets what production would hold.
        """
        for kline in klines:
            key = (kline.symbol, _interval_value(kline.interval))
            self._series.setdefault(key, {})[kline.open_time] = kline

    def load(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        limit: int = DEFAULT_KLINE_LIMIT,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        newest_first: bool = False,
    ) -> tuple[MarketData, ...]:
        self.reads.append(
            KlineRead(
                symbols=(symbol,),
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
                newest_first=newest_first,
            )
        )
        return self._rows(
            symbol,
            interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            newest_first=newest_first,
        )

    def load_many(
        self,
        symbols: Sequence[str],
        interval: TimeFrame,
        *,
        limit: int = DEFAULT_KLINE_LIMIT,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        newest_first: bool = False,
    ) -> Mapping[str, tuple[MarketData, ...]]:
        requested = tuple(symbols)
        self.reads.append(
            KlineRead(
                symbols=requested,
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
                newest_first=newest_first,
            )
        )
        return {
            symbol: self._rows(
                symbol,
                interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
                newest_first=newest_first,
            )
            for symbol in requested
        }

    # -- what a consumer's test usually wants to know ------------------------

    def was_read_for(self, symbol: str, interval: TimeFrame | None = None) -> bool:
        """Whether any read named this symbol (optionally at one interval)."""
        return any(
            symbol in read.symbols and (interval is None or read.interval == interval)
            for read in self.reads
        )

    # -- internals -----------------------------------------------------------

    def _rows(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        limit: int,
        start_time: datetime | None,
        end_time: datetime | None,
        newest_first: bool,
    ) -> tuple[MarketData, ...]:
        series = self._series.get((symbol, _interval_value(interval)), {})
        ordered = sorted(series, reverse=newest_first)
        selected = [
            series[open_time]
            for open_time in ordered
            if (start_time is None or open_time >= start_time)
            and (end_time is None or open_time <= end_time)
        ]
        return tuple(selected[:limit])
