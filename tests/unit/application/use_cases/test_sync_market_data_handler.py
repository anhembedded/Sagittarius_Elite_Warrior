from datetime import UTC, datetime
from unittest.mock import ANY, Mock

import pytest

from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data import (
    SyncMarketDataCommand,
    SyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@pytest.fixture
def mock_exchange_client():
    return Mock()


@pytest.fixture
def mock_repo():
    return Mock()


@pytest.fixture
def mock_event_bus():
    return Mock()


@pytest.fixture
def handler(mock_exchange_client, mock_repo, mock_event_bus):
    return SyncMarketDataCommandHandler(mock_exchange_client, mock_repo, mock_event_bus)


def test_sync_empty_db(handler, mock_exchange_client, mock_repo):
    # Setup: repo returns None (empty DB)
    mock_repo.get_latest_kline_time.return_value = None

    mock_klines = [Mock(spec=MarketData)]
    mock_exchange_client.get_historical_klines.return_value = mock_klines

    command = SyncMarketDataCommand(
        symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE, days_back_if_empty=5
    )
    handler.execute(command)

    # Assert get_latest_kline_time called
    mock_repo.get_latest_kline_time.assert_called_once_with(
        "BTCUSDT", TimeFrame.ONE_MINUTE
    )

    # Assert get_historical_klines called with datetime ~5 days ago
    call_args = mock_exchange_client.get_historical_klines.call_args[0]
    assert call_args[0] == "BTCUSDT"
    assert call_args[1] == TimeFrame.ONE_MINUTE
    assert isinstance(call_args[2], datetime)

    # Assert save_klines called
    mock_repo.save_klines.assert_called_once_with(mock_klines)


def test_sync_existing_data(handler, mock_exchange_client, mock_repo):
    # Setup: repo returns a specific datetime
    latest_time = datetime(2023, 1, 1, tzinfo=UTC)
    mock_repo.get_latest_kline_time.return_value = latest_time

    mock_klines = [Mock(spec=MarketData)]
    mock_exchange_client.get_historical_klines.return_value = mock_klines

    command = SyncMarketDataCommand(symbols=["ETHUSDT"], interval=TimeFrame.ONE_HOUR)
    handler.execute(command)

    # 5th arg is the per-symbol progress callback (SingleSyncProgressEvent) —
    # a fresh closure each call, so it can't be compared by equality.
    mock_exchange_client.get_historical_klines.assert_called_once_with(
        "ETHUSDT", TimeFrame.ONE_HOUR, latest_time, None, ANY
    )
    mock_repo.save_klines.assert_called_once_with(mock_klines)


def test_sync_explicit_time_range(handler, mock_exchange_client, mock_repo):
    # Setup: repo should NOT be called to get latest_time
    mock_klines = [Mock(spec=MarketData)]
    mock_exchange_client.get_historical_klines.return_value = mock_klines

    start_time = datetime(2024, 1, 1, tzinfo=UTC)
    end_time = datetime(2024, 1, 2, tzinfo=UTC)

    command = SyncMarketDataCommand(
        symbols=["SOLUSDT"],
        interval=TimeFrame.ONE_HOUR,
        start_time=start_time,
        end_time=end_time,
    )
    handler.execute(command)

    mock_repo.get_latest_kline_time.assert_not_called()
    mock_exchange_client.get_historical_klines.assert_called_once_with(
        "SOLUSDT", TimeFrame.ONE_HOUR, start_time, end_time, ANY
    )
    mock_repo.save_klines.assert_called_once_with(mock_klines)


def test_sync_no_new_data(handler, mock_exchange_client, mock_repo):
    mock_repo.get_latest_kline_time.return_value = datetime.now(UTC)
    # Exchange returns empty list
    mock_exchange_client.get_historical_klines.return_value = []

    command = SyncMarketDataCommand(symbols=["BNBUSDT"], interval=TimeFrame.ONE_DAY)
    handler.execute(command)

    # Assert save_klines is NOT called because there's no new data
    mock_repo.save_klines.assert_not_called()


def test_sync_multiple_symbols(handler, mock_exchange_client, mock_repo):
    mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.get_historical_klines.return_value = []

    command = SyncMarketDataCommand(
        symbols=["BTCUSDT", "ETHUSDT"], interval=TimeFrame.ONE_MINUTE
    )
    handler.execute(command)

    assert mock_repo.get_latest_kline_time.call_count == 2
    assert mock_exchange_client.get_historical_klines.call_count == 2


def test_sync_exchange_exception(handler, mock_exchange_client, mock_repo):
    # If exchange throws exception, handler should raise it or handle it.
    # Currently, it propagates the exception.
    mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.get_historical_klines.side_effect = Exception("API Error")

    command = SyncMarketDataCommand(symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE)

    with pytest.raises(Exception, match="API Error"):
        handler.execute(command)

    mock_repo.save_klines.assert_not_called()
