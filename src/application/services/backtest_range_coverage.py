"""Business contract for deciding whether a backtest range is safe to run."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class BacktestRangeCoverage:
    """Coverage result for a half-open historical interval.

    ``missing_open_times`` contains the first missing candle opens only.  The
    caller gets a precise diagnostic without retaining a potentially huge list
    when a database range has many gaps.
    """

    is_fully_covered: bool
    first_open_time: datetime | None
    last_open_time: datetime | None
    expected_candles: int
    actual_candles: int
    duplicate_candles: int
    missing_open_times: tuple[datetime, ...]
    has_unclosed_candle: bool


def build_backtest_range_coverage(
    snapshot: RangeCoverageSnapshot,
    timeframe: TimeFrame,
    *,
    start_time: datetime | None,
    end_time: datetime,
    now: datetime,
) -> BacktestRangeCoverage:
    """Convert a compact repository aggregate into the business contract."""
    interval_seconds = timeframe.to_seconds()
    interval = timedelta(seconds=interval_seconds)
    closed_end = _floor_open_time(
        min(_as_utc(end_time), _as_utc(now)), interval_seconds
    )
    start = (
        _ceil_open_time(_as_utc(start_time), interval_seconds)
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
        missing_open_times=tuple(dict.fromkeys(missing))[:3],
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
    end = min(_as_utc(end_time), _as_utc(now))
    closed_end = _floor_open_time(end, interval_seconds)
    ordered = sorted(
        (kline for kline in klines if kline.open_time),
        key=lambda kline: _as_utc(kline.open_time),
    )
    available_opens = [_as_utc(kline.open_time) for kline in ordered]
    first_available = available_opens[0] if available_opens else None
    start = (
        _ceil_open_time(_as_utc(start_time), interval_seconds)
        if start_time
        else first_available
    )
    scoped = [
        kline
        for kline in ordered
        if start is not None and start <= _as_utc(kline.open_time) < closed_end
    ]
    opens = [_as_utc(kline.open_time) for kline in scoped]
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
                _as_utc(kline.close_time) > _as_utc(now)
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
        _as_utc(kline.close_time) > _as_utc(now) for kline in scoped if kline.close_time
    )
    return BacktestRangeCoverage(
        is_fully_covered=not missing and duplicates == 0 and not has_unclosed,
        first_open_time=first,
        last_open_time=opens[-1] if opens else None,
        expected_candles=len(expected),
        actual_candles=len(opens),
        duplicate_candles=duplicates,
        missing_open_times=missing[:3],
        has_unclosed_candle=has_unclosed,
    )


def as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def floor_open_time(value: datetime, interval_seconds: int) -> datetime:
    return datetime.fromtimestamp(
        int(value.timestamp()) // interval_seconds * interval_seconds, UTC
    )


def ceil_open_time(value: datetime, interval_seconds: int) -> datetime:
    timestamp = int(value.timestamp())
    aligned = (timestamp + interval_seconds - 1) // interval_seconds * interval_seconds
    return datetime.fromtimestamp(aligned, UTC)


_as_utc = as_utc
_floor_open_time = floor_open_time
_ceil_open_time = ceil_open_time
