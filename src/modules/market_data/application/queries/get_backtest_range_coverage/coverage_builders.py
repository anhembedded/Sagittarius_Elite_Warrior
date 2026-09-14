"""Deciding whether a stored range is complete — two routes to one verdict.

Both functions return the same `BacktestRangeCoverage`; they differ in what they
are given, and that difference is the point:

| Route | Input | Cost | Who calls it |
| :--- | :--- | :--- | :--- |
| `build_backtest_range_coverage` | a `RangeCoverageSnapshot` — five aggregates the database computed | one `SELECT`, no candles in memory | the query handler, on every range the user picks |
| `evaluate_backtest_range_coverage` | the candles themselves | the whole range in memory | tests, and any caller that already holds the list |

The snapshot route is the one the UI uses, because a year of 1-minute candles is
half a million rows and the screen asks this question on every date change. It
can only report the *first* gap the database found, so its `missing_open_times`
is a sample; the in-memory route sees every hole. Neither is the "real" one — a
single implementation would either load half a million rows to answer a
question about their count, or force a caller holding candles to write them to
a database first.

`is_fully_covered` means the same thing in both: the range starts exactly on the
requested open, ends on the last candle that has closed, has no gap, no
duplicate, and no still-forming candle. A backtest run on anything less is
reporting a result for a range it did not actually have.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    MAX_REPORTED_MISSING_OPENS,
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.domain.candle_time import (
    as_utc,
    ceil_open_time,
    floor_open_time,
)


def build_backtest_range_coverage(
    snapshot: RangeCoverageSnapshot,
    timeframe: TimeFrame,
    *,
    start_time: datetime | None,
    end_time: datetime,
    now: datetime,
) -> BacktestRangeCoverage:
    """Convert a compact repository aggregate into the published verdict."""
    interval_seconds = timeframe.to_seconds()
    interval = timedelta(seconds=interval_seconds)
    closed_end = floor_open_time(min(as_utc(end_time), as_utc(now)), interval_seconds)
    start = (
        ceil_open_time(as_utc(start_time), interval_seconds)
        if start_time
        else snapshot.first_record
    )
    if start is None or start >= closed_end:
        return BacktestRangeCoverage(
            is_fully_covered=False,
            first_open_time=snapshot.first_record,
            last_open_time=snapshot.last_record,
            expected_candles=0,
            actual_candles=snapshot.total_candles,
            duplicate_candles=snapshot.total_candles - snapshot.distinct_candles,
            missing_open_times=(),
            has_unclosed_candle=snapshot.unclosed_candles > 0,
        )

    expected_candles = int((closed_end - start).total_seconds()) // interval_seconds
    expected_last = closed_end - interval
    # Three places a hole can show up in an aggregate, in the order a reader
    # would look for them: before the first stored candle, somewhere in the
    # middle (the database reports only the first such gap), and after the last
    # one. `dict.fromkeys` de-duplicates while keeping that order.
    missing: list[datetime] = []
    if snapshot.first_record is None or snapshot.first_record > start:
        missing.append(start)
    if snapshot.first_gap_after is not None:
        missing.append(snapshot.first_gap_after + interval)
    if snapshot.last_record is not None and snapshot.last_record < expected_last:
        missing.append(snapshot.last_record + interval)
    duplicates = snapshot.total_candles - snapshot.distinct_candles
    fully_covered = (
        snapshot.first_record == start
        and snapshot.last_record == expected_last
        and snapshot.distinct_candles == expected_candles
        and duplicates == 0
        and snapshot.first_gap_after is None
        and snapshot.unclosed_candles == 0
    )
    return BacktestRangeCoverage(
        is_fully_covered=fully_covered,
        first_open_time=snapshot.first_record,
        last_open_time=snapshot.last_record,
        expected_candles=expected_candles,
        actual_candles=snapshot.total_candles,
        duplicate_candles=duplicates,
        missing_open_times=tuple(dict.fromkeys(missing))[:MAX_REPORTED_MISSING_OPENS],
        has_unclosed_candle=snapshot.unclosed_candles > 0,
    )


def evaluate_backtest_range_coverage(
    klines: list[MarketData],
    timeframe: TimeFrame,
    *,
    start_time: datetime | None,
    end_time: datetime,
    now: datetime,
) -> BacktestRangeCoverage:
    """Evaluate cadence and closed-candle coverage for ``[start, end)``.

    ``start_time=None`` means the oldest locally available candle defines the
    requested lower bound; an unbounded "all history" request cannot claim an
    exchange-wide start that the user did not specify.
    """
    interval_seconds = timeframe.to_seconds()
    end = min(as_utc(end_time), as_utc(now))
    closed_end = floor_open_time(end, interval_seconds)
    ordered = sorted(
        (kline for kline in klines if kline.open_time),
        key=lambda kline: as_utc(kline.open_time),
    )
    available_opens = [as_utc(kline.open_time) for kline in ordered]
    first_available = available_opens[0] if available_opens else None
    start = (
        ceil_open_time(as_utc(start_time), interval_seconds)
        if start_time
        else first_available
    )
    scoped = [
        kline
        for kline in ordered
        if start is not None and start <= as_utc(kline.open_time) < closed_end
    ]
    opens = [as_utc(kline.open_time) for kline in scoped]
    first = opens[0] if opens else None
    if start is None or start >= closed_end:
        return BacktestRangeCoverage(
            is_fully_covered=False,
            first_open_time=first,
            last_open_time=opens[-1] if opens else None,
            expected_candles=0,
            actual_candles=len(opens),
            duplicate_candles=len(opens) - len(set(opens)),
            missing_open_times=(),
            has_unclosed_candle=any(
                as_utc(kline.close_time) > as_utc(now)
                for kline in scoped
                if kline.close_time
            ),
        )

    expected = tuple(
        datetime.fromtimestamp(timestamp, UTC)
        for timestamp in range(
            int(start.timestamp()), int(closed_end.timestamp()), interval_seconds
        )
    )
    open_set = set(opens)
    missing = tuple(open_time for open_time in expected if open_time not in open_set)
    duplicates = len(opens) - len(open_set)
    has_unclosed = any(
        as_utc(kline.close_time) > as_utc(now) for kline in scoped if kline.close_time
    )
    return BacktestRangeCoverage(
        is_fully_covered=not missing and duplicates == 0 and not has_unclosed,
        first_open_time=first,
        last_open_time=opens[-1] if opens else None,
        expected_candles=len(expected),
        actual_candles=len(opens),
        duplicate_candles=duplicates,
        missing_open_times=missing[:MAX_REPORTED_MISSING_OPENS],
        has_unclosed_candle=has_unclosed,
    )
