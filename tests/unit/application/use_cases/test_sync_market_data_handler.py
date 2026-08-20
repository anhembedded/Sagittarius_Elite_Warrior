from datetime import UTC, datetime
from unittest.mock import ANY, Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    ExchangeRequestCancelled,
)
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
    mock_exchange_client.stream_historical_klines.return_value = iter([mock_klines])

    command = SyncMarketDataCommand(
        symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE, days_back_if_empty=5
    )
    handler.execute(command)

    # Assert get_latest_kline_time called
    mock_repo.get_latest_kline_time.assert_called_once_with(
        "BTCUSDT", TimeFrame.ONE_MINUTE
    )

    # Assert stream_historical_klines called with datetime ~5 days ago
    call_args = mock_exchange_client.stream_historical_klines.call_args[0]
    assert call_args[0] == "BTCUSDT"
    assert call_args[1] == TimeFrame.ONE_MINUTE
    assert isinstance(call_args[2], datetime)

    # Assert save_klines called with the single yielded chunk
    mock_repo.save_klines.assert_called_once_with(mock_klines)


def test_sync_existing_data(handler, mock_exchange_client, mock_repo):
    # Setup: repo returns a specific datetime
    latest_time = datetime(2023, 1, 1, tzinfo=UTC)
    mock_repo.get_latest_kline_time.return_value = latest_time

    mock_klines = [Mock(spec=MarketData)]
    mock_exchange_client.stream_historical_klines.return_value = iter([mock_klines])

    command = SyncMarketDataCommand(symbols=["ETHUSDT"], interval=TimeFrame.ONE_HOUR)
    handler.execute(command)

    # 5th arg is the per-symbol progress callback (SingleSyncProgressEvent) —
    # a fresh closure each call, so it can't be compared by equality.
    mock_exchange_client.stream_historical_klines.assert_called_once_with(
        "ETHUSDT", TimeFrame.ONE_HOUR, latest_time, None, ANY, None
    )
    mock_repo.save_klines.assert_called_once_with(mock_klines)


def test_sync_explicit_time_range(handler, mock_exchange_client, mock_repo):
    # Setup: repo should NOT be called to get latest_time
    mock_klines = [Mock(spec=MarketData)]
    mock_exchange_client.stream_historical_klines.return_value = iter([mock_klines])

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
    mock_exchange_client.stream_historical_klines.assert_called_once_with(
        "SOLUSDT", TimeFrame.ONE_HOUR, start_time, end_time, ANY, None
    )
    mock_repo.save_klines.assert_called_once_with(mock_klines)


def test_sync_no_new_data(handler, mock_exchange_client, mock_repo):
    mock_repo.get_latest_kline_time.return_value = datetime.now(UTC)
    # Exchange yields no chunks at all
    mock_exchange_client.stream_historical_klines.return_value = iter([])

    command = SyncMarketDataCommand(symbols=["BNBUSDT"], interval=TimeFrame.ONE_DAY)
    handler.execute(command)

    # Assert save_klines is NOT called because there's no new data
    mock_repo.save_klines.assert_not_called()


def test_sync_multiple_symbols(handler, mock_exchange_client, mock_repo):
    mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.stream_historical_klines.side_effect = lambda *a, **kw: iter(
        []
    )

    command = SyncMarketDataCommand(
        symbols=["BTCUSDT", "ETHUSDT"], interval=TimeFrame.ONE_MINUTE
    )
    handler.execute(command)

    assert mock_repo.get_latest_kline_time.call_count == 2
    assert mock_exchange_client.stream_historical_klines.call_count == 2


def test_sync_exchange_exception(handler, mock_exchange_client, mock_repo):
    # If exchange throws exception, handler should raise it or handle it.
    # Currently, it propagates the exception.
    mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.stream_historical_klines.side_effect = Exception("API Error")

    command = SyncMarketDataCommand(symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE)

    with pytest.raises(Exception, match="API Error"):
        handler.execute(command)

    mock_repo.save_klines.assert_not_called()


def test_cancelled_sync_never_persists_partial_exchange_data(
    handler, mock_exchange_client, mock_repo
):
    mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.stream_historical_klines.side_effect = (
        ExchangeRequestCancelled("cancelled")
    )
    command = SyncMarketDataCommand(
        symbols=["BTCUSDT"],
        interval=TimeFrame.ONE_MINUTE,
        cancellation_requested=lambda: False,
    )

    handler.execute(command)

    mock_repo.save_klines.assert_not_called()


def test_cancellation_mid_stream_stops_before_saving_the_in_flight_chunk(
    handler, mock_exchange_client, mock_repo
):
    """A chunk already fetched before cancellation was observed must never
    be persisted — cancellation is checked before each save, not just once
    up front (BUG-025's streaming rewrite widened the cancellation window
    from "before the whole sync" to "before every chunk")."""
    mock_repo.get_latest_kline_time.return_value = None
    chunk_a = [Mock(spec=MarketData)]
    chunk_b = [Mock(spec=MarketData)]
    mock_exchange_client.stream_historical_klines.return_value = iter(
        [chunk_a, chunk_b]
    )

    # 1st call is execute()'s own pre-symbol-loop check, 2nd is the check
    # right before saving chunk_a, 3rd is the one right before chunk_b.
    cancel_before_second_chunk = Mock(side_effect=[False, False, True])
    command = SyncMarketDataCommand(
        symbols=["BTCUSDT"],
        interval=TimeFrame.ONE_MINUTE,
        cancellation_requested=cancel_before_second_chunk,
    )
    handler.execute(command)

    mock_repo.save_klines.assert_called_once_with(chunk_a)


def test_sync_streams_each_chunk_to_the_db_as_it_arrives_instead_of_buffering_the_whole_range(
    handler, mock_exchange_client, mock_repo
):
    """BUG-025 regression test: the handler must persist every fetched
    chunk immediately, not accumulate the entire requested range into one
    list and call save_klines() a single time at the end. Before the fix,
    the handler called `get_historical_klines()` (whole-range, no
    chunking) and this test's `stream_historical_klines` mock was never
    consulted at all, so `save_klines` would not be called with either
    chunk here — proving the old code path bypassed streaming entirely."""
    mock_repo.get_latest_kline_time.return_value = None
    chunk_a = [Mock(spec=MarketData), Mock(spec=MarketData)]
    chunk_b = [Mock(spec=MarketData), Mock(spec=MarketData)]
    mock_exchange_client.stream_historical_klines.return_value = iter(
        [chunk_a, chunk_b]
    )

    command = SyncMarketDataCommand(
        symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE, days_back_if_empty=5
    )
    handler.execute(command)

    assert mock_repo.save_klines.call_count == 2
    mock_repo.save_klines.assert_any_call(chunk_a)
    mock_repo.save_klines.assert_any_call(chunk_b)
