from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    build_backtest_range_coverage,
    evaluate_backtest_range_coverage,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def _candle(open_time: datetime, *, close_time: datetime | None = None) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        interval="1h",
        open_time=open_time,
        close_time=close_time or open_time + timedelta(hours=1),
        open_price=1.0,
        high_price=1.0,
        low_price=1.0,
        close_price=1.0,
        volume=1.0,
        quote_asset_volume=1.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=1.0,
        taker_buy_quote_asset_volume=1.0,
    )


_START = datetime(2026, 1, 1, tzinfo=UTC)
_NOW = _START + timedelta(hours=5, minutes=30)


def _coverage(klines: list[MarketData]):
    return evaluate_backtest_range_coverage(
        klines, TimeFrame.ONE_HOUR, start_time=_START, end_time=_NOW, now=_NOW
    )


def test_complete_closed_candle_range_is_covered():
    result = _coverage([_candle(_START + timedelta(hours=index)) for index in range(5)])

    assert result.is_fully_covered is True
    assert result.expected_candles == 5


def test_internal_gap_and_boundary_gap_are_not_covered():
    result = _coverage([_candle(_START), _candle(_START + timedelta(hours=2))])

    assert result.is_fully_covered is False
    assert result.missing_open_times == (
        _START + timedelta(hours=1),
        _START + timedelta(hours=3),
        _START + timedelta(hours=4),
    )


def test_duplicate_and_unclosed_candle_are_not_covered():
    result = _coverage(
        [_candle(_START + timedelta(hours=index)) for index in range(5)]
        + [_candle(_START, close_time=_NOW + timedelta(minutes=1))]
    )

    assert result.is_fully_covered is False
    assert result.duplicate_candles == 1
    assert result.has_unclosed_candle is True


def test_candles_at_half_open_end_are_excluded():
    result = _coverage([_candle(_START + timedelta(hours=index)) for index in range(6)])

    assert result.is_fully_covered is True
    assert result.actual_candles == 5


def test_compact_snapshot_detects_internal_gap_without_loading_entities():
    snapshot = RangeCoverageSnapshot(
        first_record=_START,
        last_record=_START + timedelta(hours=4),
        total_candles=4,
        distinct_candles=4,
        first_gap_after=_START + timedelta(hours=1),
        unclosed_candles=0,
    )

    result = build_backtest_range_coverage(
        snapshot,
        TimeFrame.ONE_HOUR,
        start_time=_START,
        end_time=_NOW,
        now=_NOW,
    )

    assert result.is_fully_covered is False
    assert result.missing_open_times == (_START + timedelta(hours=2),)
