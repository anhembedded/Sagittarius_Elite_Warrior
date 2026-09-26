"""The verified fake for `IMarketDataRepository` (HLD §10.3).

**Public API.** Three backtest handlers read market history through this port;
with this fake they can be tested without a database, and without each of them
writing its own stand-in that drifts.

**There was already an in-memory one, and it was not fit to publish.**
`tests/integration/golden/fakes/in_memory_market_data_repository.py` served the
golden master and said so in its own docstring ("the write and maintenance side
is inert"). Handing that to a consumer would have been worse than a `Mock`,
because it looks like a real implementation while:

- `save_klines()` **replaced** the whole store instead of upserting, so two
  saves lost the first one — the real repository upserts on
  `(symbol, interval, open_time)`;
- `clear_klines()` and `purge_all()` returned `0` and deleted nothing, so a test
  could "clear" a symbol and still read it back;
- `get_gaps()` always returned `[]`, so a consumer asserting "a gap is
  detected" would pass against data full of holes;
- `get_database_status()`, `get_database_status_for_intervals()` and
  `get_range_coverage()` raised `NotImplementedError`.

This one implements every method and passes
`contract_market_data_repository.py`, the same suite `SQLAlchemyMarketDataRepository`
passes. That is the difference between an in-memory object and a *verified* one.

**Storage**: one dict per `(market, symbol, interval)` keyed by `open_time`.
`EPIC-027A` added `market` to the key, mirroring the real repository's
market-qualified shards — Spot and Futures candles of the same symbol and
interval never collide here either. Upsert is then a plain assignment, and
ordering is `sorted()` over the keys — the two things the real repository gets
from a primary key and an `ORDER BY`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from itertools import pairwise

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    DatabaseStatusSnapshot,
    IMarketDataRepository,
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.domain.data_gap import DataGap

#: `(market, symbol, interval value)` -> `{open_time: candle}`.
_Series = dict[datetime, MarketData]
_SeriesKey = tuple[MarketType, str, str]


def _interval_value(interval: TimeFrame | str) -> str:
    """`TimeFrame` is a `str` enum, and both spellings occur in this repository
    — `MarketData.interval` is declared `str` but existing tests construct it
    with the enum, which satisfies the annotation because the enum *is* a str.
    Normalising here means the fake keys the same way whichever arrives, rather
    than silently storing two series for one interval."""
    return interval.value if isinstance(interval, TimeFrame) else str(interval)


class FakeMarketDataRepository(IMarketDataRepository):
    """Market history in dicts, with the real repository's semantics."""

    def __init__(
        self, klines: list[MarketData] | None = None, market: MarketType = MarketType.SPOT
    ) -> None:
        """`klines` seeds the store exactly as `save_klines()` would, so a
        consumer's test arranges its history in one line. `market` names which
        market those seed candles belong to (defaults to Spot, today's only
        real source — `binance_endpoints.py`)."""
        self._series: dict[_SeriesKey, _Series] = {}
        #: Every `vacuum()` call, in order. The real one rewrites the SQLite
        #: file; there is nothing to rewrite here, but a caller that must prove
        #: it asked needs something to assert against, and a silent no-op would
        #: give it nothing.
        self.vacuum_calls: list[tuple[MarketType, str | None]] = []
        if klines:
            self.save_klines(market, klines)

    # -- writing -------------------------------------------------------------

    def save_klines(self, market: MarketType, klines: list[MarketData]) -> None:
        for kline in klines:
            key = (market, kline.symbol, _interval_value(kline.interval))
            # Upsert, like the real primary key: the same open_time arriving
            # again replaces the row rather than duplicating it. A sync that
            # re-fetches an overlapping window depends on this.
            self._series.setdefault(key, {})[kline.open_time] = kline

    def clear_klines(
        self, market: MarketType, symbol: str, interval: TimeFrame | None = None
    ) -> int:
        removed = 0
        for key in list(self._series):
            if key[0] != market or key[1] != symbol:
                continue
            if interval is not None and key[2] != _interval_value(interval):
                continue
            removed += len(self._series.pop(key))
        return removed

    def purge_all(self) -> int:
        removed = sum(len(series) for series in self._series.values())
        self._series.clear()
        return removed

    def vacuum(self, market: MarketType, symbol: str | None = None) -> None:
        self.vacuum_calls.append((market, symbol))

    # -- reading -------------------------------------------------------------

    def _rows(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        """The rows a query selects, ordered. Bounds are **inclusive** on both
        ends, which is what the real `get_klines()` does — `get_range_coverage()`
        is the one half-open reader and computes its own bounds."""
        series = self._series.get((market, symbol, _interval_value(interval)), {})
        times = sorted(series, reverse=order_by_desc)
        return [
            series[open_time]
            for open_time in times
            if (start_time is None or open_time >= start_time)
            and (end_time is None or open_time <= end_time)
        ]

    def get_klines(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        rows = self._rows(market, symbol, interval, start_time, end_time, order_by_desc)
        return rows[:limit] if limit is not None else rows

    def count_klines(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        return len(
            self.get_klines(market, symbol, interval, start_time, end_time, limit)
        )

    def stream_klines(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> Iterator[MarketData]:
        rows = self._rows(market, symbol, interval, start_time, end_time, order_by_desc)
        if offset is not None:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        yield from rows

    def get_latest_kline_time(
        self, market: MarketType, symbol: str, interval: TimeFrame
    ) -> datetime | None:
        series = self._series.get((market, symbol, _interval_value(interval)), {})
        return max(series) if series else None

    def has_any_klines(self, market: MarketType, symbol: str) -> bool:
        # Interval-agnostic on purpose (`BUG-078`): a caller deciding whether a
        # symbol's storage is safe to delete must not judge "empty" against
        # only the intervals the UI happens to show.
        return any(
            key[0] == market and key[1] == symbol and series
            for key, series in self._series.items()
        )

    def list_available_shards(self, market: MarketType) -> list[str]:
        return sorted(
            {key[1] for key, series in self._series.items() if key[0] == market and series}
        )

    # -- reporting -----------------------------------------------------------

    def get_database_status(
        self, market: MarketType, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        rows = self._rows(market, symbol, interval)
        if not rows:
            return DatabaseStatusSnapshot(
                first_record=None, last_record=None, total_candles=0, gaps=0
            )
        return DatabaseStatusSnapshot(
            first_record=rows[0].open_time,
            last_record=rows[-1].open_time,
            total_candles=len(rows),
            gaps=len(self._discontinuities(rows, interval)),
        )

    def get_database_status_for_intervals(
        self, market: MarketType, symbol: str, intervals: list[TimeFrame]
    ) -> dict[str, DatabaseStatusSnapshot]:
        # Keyed by `TimeFrame.value`, and every requested interval is present
        # even when it holds nothing — a caller scanning a grid renders a row
        # per interval and must not have to guess at a missing key.
        return {
            interval.value: self.get_database_status(market, symbol, interval)
            for interval in intervals
        }

    def get_gaps(
        self, market: MarketType, symbol: str, interval: TimeFrame
    ) -> list[DataGap]:
        rows = self._rows(market, symbol, interval)
        cadence = timedelta(seconds=interval.to_seconds())
        return [
            DataGap(
                symbol=symbol,
                interval=interval,
                start_time=before.open_time,
                end_time=after.open_time,
                missing_candles=max(
                    1,
                    int((after.open_time - before.open_time) / cadence) - 1,
                ),
            )
            for before, after in self._discontinuities(rows, interval)
        ]

    def get_range_coverage(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> RangeCoverageSnapshot:
        """Aggregates for the **half-open** `[start_time, end_time)`.

        Half-open, unlike every other reader here, because the caller is asking
        "is this backtest range complete?" and the candle opening exactly at
        `end_time` belongs to the next range, not this one.
        """
        rows = [
            row
            for row in self._rows(market, symbol, interval)
            if (start_time is None or row.open_time >= start_time)
            and row.open_time < end_time
        ]
        if not rows:
            return RangeCoverageSnapshot(
                first_record=None,
                last_record=None,
                total_candles=0,
                distinct_candles=0,
                first_gap_after=None,
                unclosed_candles=0,
            )

        discontinuities = self._discontinuities(rows, interval)
        # Named rather than counted inline: `sum(1 for ...)` reads as arithmetic
        # where this is a filter, and mypy resolves that generator to the wrong
        # `sum()` overload anyway.
        still_forming = [row for row in rows if row.close_time and row.close_time > now]
        return RangeCoverageSnapshot(
            first_record=rows[0].open_time,
            last_record=rows[-1].open_time,
            total_candles=len(rows),
            # Equal to `total_candles` here, and that is not a shortcut: the
            # store is keyed by open_time, so a duplicate cannot exist. The
            # real one counts both because a database can hold one.
            distinct_candles=len({row.open_time for row in rows}),
            first_gap_after=discontinuities[0][0].open_time
            if discontinuities
            else None,
            unclosed_candles=len(still_forming),
        )

    @staticmethod
    def _discontinuities(
        rows: list[MarketData], interval: TimeFrame
    ) -> list[tuple[MarketData, MarketData]]:
        """Consecutive pairs with more than one cadence between them.

        This is what "gaps" counts, and it is a **run** count, not a missing-
        candle count: three candles missing in a row is one gap. The real
        repository's SQL does the same, and the difference is visible —
        `get_database_status().gaps` reads `1` for a five-minute hole in
        one-minute data, while that hole's `DataGap.missing_candles` reads `4`.
        """
        cadence = timedelta(seconds=interval.to_seconds())
        return [
            (before, after)
            for before, after in pairwise(rows)
            if after.open_time - before.open_time > cadence
        ]
