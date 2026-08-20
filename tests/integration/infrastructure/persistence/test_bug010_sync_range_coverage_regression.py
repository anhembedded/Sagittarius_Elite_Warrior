"""Regression test for BUG-010: "Đồng bộ dữ liệu ngay" never satisfies Backtest range coverage.

Verifies that when SQLite repository contains closed candles up to (now - 1 interval)
plus a currently forming (unclosed) candle fetched during sync, get_range_coverage
and build_backtest_range_coverage correctly evaluate the closed-candle window
without falsely failing on the unclosed candle.
"""

from datetime import UTC, datetime, timedelta

import pytest

from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    build_backtest_range_coverage,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)


@pytest.fixture
def repo(tmp_path):
    db_config = DatabaseConfig(db_dir=str(tmp_path))
    db_manager = DatabaseManager(db_config)
    repository = SQLAlchemyMarketDataRepository(db_manager)
    yield repository
    db_manager.dispose_all()


def _kline(symbol: str, open_time: datetime, close_time: datetime) -> MarketData:
    return MarketData(
        symbol=symbol,
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        close_time=close_time,
        open_price=100.0,
        high_price=105.0,
        low_price=95.0,
        close_price=102.0,
        volume=10.0,
        quote_asset_volume=1020.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=510.0,
    )


def test_bug010_unclosed_forming_candle_does_not_break_range_coverage(repo):
    # Simulated scenario from BUG-010:
    # 5 closed 1m candles: 10:36:00 to 10:40:00
    # 1 unclosed 1m candle: 10:41:00 (closing at 10:41:59.999)
    # Current time `now`: 10:41:35 (mid-bar for 10:41)
    base_time = datetime(2026, 8, 18, 10, 36, tzinfo=UTC)
    now = datetime(2026, 8, 18, 10, 41, 35, tzinfo=UTC)

    candles = [
        _kline(
            "BTCUSDT",
            base_time + timedelta(minutes=i),
            base_time + timedelta(minutes=i + 1) - timedelta(milliseconds=1),
        )
        for i in range(5)  # 10:36, 10:37, 10:38, 10:39, 10:40 (all closed)
    ]
    # Add the forming/unclosed 10:41 candle
    candles.append(
        _kline(
            "BTCUSDT",
            datetime(2026, 8, 18, 10, 41, tzinfo=UTC),
            datetime(2026, 8, 18, 10, 41, 59, 999000, tzinfo=UTC),
        )
    )
    repo.save_klines(candles)

    # Test "Toàn bộ lịch sử" (All history): start_time=None, end_time=now
    snapshot = repo.get_range_coverage(
        "BTCUSDT",
        TimeFrame.ONE_MINUTE,
        start_time=None,
        end_time=now,
        now=now,
    )

    coverage = build_backtest_range_coverage(
        snapshot,
        TimeFrame.ONE_MINUTE,
        start_time=None,
        end_time=now,
        now=now,
    )

    assert coverage.is_fully_covered is True
    assert coverage.expected_candles == 5
    assert coverage.actual_candles == 5
    assert coverage.has_unclosed_candle is False
    assert coverage.missing_open_times == ()
    assert coverage.first_open_time == base_time
    assert coverage.last_open_time == datetime(2026, 8, 18, 10, 40, tzinfo=UTC)
