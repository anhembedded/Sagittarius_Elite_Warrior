from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)


def _make_candle(symbol: str, interval: TimeFrame, open_time: datetime) -> MarketData:
    close_time = open_time + timedelta(seconds=interval.to_seconds())
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        open_price=100.0,
        high_price=105.0,
        low_price=99.0,
        close_price=103.0,
        volume=10.0,
        close_time=close_time,
        quote_asset_volume=1030.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=515.0,
    )


def test_repository_detects_no_gaps_in_contiguous_series():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(DatabaseConfig(db_dir=tmpdir))
        repo = SQLAlchemyMarketDataRepository(db_mgr)

        try:
            t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
            # Create 10 contiguous 1m candles
            candles = [
                _make_candle("BTCUSDT", TimeFrame.ONE_MINUTE, t0 + timedelta(minutes=i))
                for i in range(10)
            ]
            repo.save_klines(candles)

            gaps = repo.get_gaps("BTCUSDT", TimeFrame.ONE_MINUTE)
            assert len(gaps) == 0
        finally:
            db_mgr.dispose_all()


def test_repository_detects_gap_between_separated_candles():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(DatabaseConfig(db_dir=tmpdir))
        repo = SQLAlchemyMarketDataRepository(db_mgr)

        try:
            t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
            c1 = _make_candle("BTCUSDT", TimeFrame.ONE_MINUTE, t0)
            # Gap of 5 minutes: next candle is at t0 + 6 minutes
            t_gap = t0 + timedelta(minutes=6)
            c2 = _make_candle("BTCUSDT", TimeFrame.ONE_MINUTE, t_gap)

            repo.save_klines([c1, c2])

            gaps = repo.get_gaps("BTCUSDT", TimeFrame.ONE_MINUTE)
            assert len(gaps) == 1
            gap = gaps[0]
            assert gap.symbol == "BTCUSDT"
            assert gap.interval == TimeFrame.ONE_MINUTE
            assert gap.start_time == t0
            assert gap.end_time == t_gap
            assert gap.missing_candles == 5
        finally:
            db_mgr.dispose_all()
