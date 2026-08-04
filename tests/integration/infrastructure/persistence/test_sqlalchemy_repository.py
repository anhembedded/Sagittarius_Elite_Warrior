import pytest
from datetime import datetime, timezone
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)


from unittest.mock import Mock


@pytest.fixture
def repo():
    # Use in-memory SQLite for testing
    config = Mock()
    config.get.return_value = "sqlite:///:memory:"
    return SQLAlchemyMarketDataRepository(config)


def create_mock_kline(symbol: str, timestamp: datetime) -> MarketData:
    return MarketData(
        symbol=symbol,
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=timestamp,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=timestamp,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def test_save_and_get_klines(repo):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=timezone.utc)

    klines = [create_mock_kline("BTCUSDT", dt1), create_mock_kline("BTCUSDT", dt2)]

    repo.save_klines(klines)

    fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)

    assert len(fetched) == 2
    assert fetched[0].open_time == dt1
    assert fetched[1].open_time == dt2
    assert fetched[0].close_price == 105.0


def test_upsert_behavior(repo):
    dt = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    kline1 = create_mock_kline("ETHUSDT", dt)

    repo.save_klines([kline1])

    # Save the same kline but with updated price (simulating an upsert)
    kline2 = create_mock_kline("ETHUSDT", dt)
    # Using object.__setattr__ because MarketData is frozen=True
    object.__setattr__(kline2, "close_price", 200.0)

    repo.save_klines([kline2])

    fetched = repo.get_klines("ETHUSDT", TimeFrame.ONE_MINUTE)

    assert len(fetched) == 1
    assert fetched[0].close_price == 200.0  # Should be updated


def test_get_latest_kline_time(repo):
    assert repo.get_latest_kline_time("BNBUSDT", TimeFrame.ONE_MINUTE) is None

    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=timezone.utc)

    repo.save_klines(
        [create_mock_kline("BNBUSDT", dt1), create_mock_kline("BNBUSDT", dt2)]
    )

    latest = repo.get_latest_kline_time("BNBUSDT", TimeFrame.ONE_MINUTE)

    assert latest == dt2


def test_get_klines_with_time_range(repo):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=timezone.utc)
    dt3 = datetime(2023, 1, 1, 12, 2, tzinfo=timezone.utc)

    repo.save_klines(
        [
            create_mock_kline("BTCUSDT", dt1),
            create_mock_kline("BTCUSDT", dt2),
            create_mock_kline("BTCUSDT", dt3),
        ]
    )

    # Query only middle point
    fetched = repo.get_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, start_time=dt2, end_time=dt2
    )
    assert len(fetched) == 1
    assert fetched[0].open_time == dt2

    # Query from middle to end
    fetched2 = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE, start_time=dt2)
    assert len(fetched2) == 2
    assert fetched2[0].open_time == dt2
    assert fetched2[1].open_time == dt3

def test_get_klines_with_limit(repo):
    from datetime import timedelta
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    klines = [create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(10)]
    repo.save_klines(klines)
    
    # Get last 3 klines
    fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE, limit=3)
    
    assert len(fetched) == 3
    # Check that they are in chronological order and represent the latest 3
    assert fetched[0].open_time == base_dt + timedelta(minutes=7)
    assert fetched[1].open_time == base_dt + timedelta(minutes=8)
    assert fetched[2].open_time == base_dt + timedelta(minutes=9)
