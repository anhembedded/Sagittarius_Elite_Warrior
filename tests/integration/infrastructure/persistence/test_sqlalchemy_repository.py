import pytest
from datetime import datetime, timezone
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Binace_Bot.src.infrastructure.persistence.database_manager import (
    DatabaseManager,
    DatabaseConfig,
)
from Binace_Bot.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)


@pytest.fixture
def repo(tmp_path):
    db_config = DatabaseConfig(db_dir=str(tmp_path))
    db_manager = DatabaseManager(db_config)
    return SQLAlchemyMarketDataRepository(db_manager)


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

    # Assert all volumes and fields to prevent silent mapping bugs
    assert fetched[0].volume == 1000.0
    assert fetched[0].quote_asset_volume == 105000.0
    assert fetched[0].number_of_trades == 50
    assert fetched[0].taker_buy_base_asset_volume == 500.0
    assert fetched[0].taker_buy_quote_asset_volume == 52500.0


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
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(10)
    ]
    repo.save_klines(klines)

    # Get last 3 klines efficiently descending
    fetched = repo.get_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, limit=3, order_by_desc=True
    )

    assert len(fetched) == 3
    # Check that they are the latest 3 in DESCENDING order
    assert fetched[0].open_time == base_dt + timedelta(minutes=9)
    assert fetched[1].open_time == base_dt + timedelta(minutes=8)
    assert fetched[2].open_time == base_dt + timedelta(minutes=7)


def test_save_klines_bulk_chunking(repo):
    from datetime import timedelta

    # Create 12000 mock klines to ensure chunking logic (5000 per chunk) is executed
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i))
        for i in range(12000)
    ]

    # This should not raise any exceptions and should insert in chunks
    repo.save_klines(klines)

    # Verify count
    fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)
    assert len(fetched) == 12000
    assert fetched[0].open_time == base_dt
    assert fetched[-1].open_time == base_dt + timedelta(minutes=11999)


def test_multi_symbol_db_separation(repo):
    from datetime import timedelta

    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)

    # Save klines for BTC and ETH in the same batch
    btc_klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(5)
    ]
    eth_klines = [
        create_mock_kline("ETHUSDT", base_dt + timedelta(minutes=i)) for i in range(5)
    ]

    repo.save_klines(btc_klines + eth_klines)

    # Retrieve independently
    btc_fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)
    eth_fetched = repo.get_klines("ETHUSDT", TimeFrame.ONE_MINUTE)

    assert len(btc_fetched) == 5
    assert len(eth_fetched) == 5

    # Ensure they don't leak into each other (symbol check is intrinsic, but we also know they use different engines)
    assert all(k.symbol == "BTCUSDT" for k in btc_fetched)
    assert all(k.symbol == "ETHUSDT" for k in eth_fetched)

    # Verify internal session pool created two engines
    assert len(repo.db_manager._sessions) == 2
    assert "BTCUSDT" in repo.db_manager._sessions
    assert "ETHUSDT" in repo.db_manager._sessions


def test_get_database_status_empty_database(repo):
    """An empty database returns a zeroed, typed DatabaseStatusSnapshot — not a dict."""
    status = repo.get_database_status("NOSUCHCOIN", TimeFrame.ONE_MINUTE)

    assert isinstance(status, DatabaseStatusSnapshot)
    assert status.first_record is None
    assert status.last_record is None
    assert status.total_candles == 0
    assert status.gaps == 0


def test_get_database_status_detects_gap(repo):
    """A missing candle between two stored ones is counted as a gap."""
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=timezone.utc)
    # dt3 skips minute 12:02 entirely -> one gap at the expected 1-minute interval.
    dt3 = datetime(2023, 1, 1, 12, 5, tzinfo=timezone.utc)

    repo.save_klines(
        [
            create_mock_kline("BTCUSDT", dt1),
            create_mock_kline("BTCUSDT", dt2),
            create_mock_kline("BTCUSDT", dt3),
        ]
    )

    status = repo.get_database_status("BTCUSDT", TimeFrame.ONE_MINUTE)

    assert isinstance(status, DatabaseStatusSnapshot)
    assert status.first_record == dt1
    assert status.last_record == dt3
    assert status.total_candles == 3
    assert status.gaps == 1
