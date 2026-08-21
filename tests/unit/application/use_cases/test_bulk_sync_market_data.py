from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data.handler import (
    BulkSyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys


class _NetworkError(Exception):
    pass


@pytest.fixture
def mock_event_bus():
    return Mock()


@pytest.fixture
def mock_config():
    config = Mock()
    # By default, use a very short sleep or 0 for tests
    config.get.return_value = 0
    return config


@pytest.fixture
def mock_dispatcher():
    return Mock()


@pytest.fixture
def handler(mock_event_bus, mock_config, mock_dispatcher):
    return BulkSyncMarketDataCommandHandler(
        event_bus=mock_event_bus, config=mock_config, dispatcher=mock_dispatcher
    )


def test_bulk_sync_empty_targets(handler, mock_event_bus, mock_dispatcher):
    cmd = BulkSyncMarketDataCommand(targets=[])
    handler.execute(cmd)

    mock_dispatcher.dispatch.assert_not_called()
    assert mock_event_bus.emit.call_count == 1

    event = mock_event_bus.emit.call_args[0][0]
    assert isinstance(event, BulkSyncProgressEvent)
    assert event.is_complete is True
    assert event.total_targets == 0


@patch("time.sleep")
def test_bulk_sync_success(
    mock_sleep, handler, mock_event_bus, mock_dispatcher, mock_config
):
    # Set config rate limit delay to 100ms
    mock_config.get.side_effect = lambda key, default: (
        100 if key == ConfigKeys.BINANCE_RATE_LIMIT_DELAY_MS.value else default
    )

    targets = [("BTCUSDT", "1m"), ("ETHUSDT", "5m")]
    cmd = BulkSyncMarketDataCommand(targets=targets)

    handler.execute(cmd)

    # Check that the dispatcher was used (DIP: no direct SyncMarketDataCommandHandler ref)
    assert mock_dispatcher.dispatch.call_count == 2

    # Verify dispatch calls
    dispatch_calls = mock_dispatcher.dispatch.call_args_list
    assert len(dispatch_calls) == 2
    symbols_dispatched = []
    for call in dispatch_calls:
        call_type, call_cmd = call[0]
        assert call_type == SyncMarketDataCommand
        assert isinstance(call_cmd, SyncMarketDataCommand)
        symbols_dispatched.append(call_cmd.symbols[0])

    # Thread pool execution might be out of order, so sort the output
    assert sorted(symbols_dispatched) == ["BTCUSDT", "ETHUSDT"]

    # Check that sleep was called exactly once (between 2 targets)
    assert mock_sleep.call_count == 1
    # Check that the sleep time is valid (could be slightly less than 0.1s due to execution overhead)
    assert 0 <= mock_sleep.call_args[0][0] <= 0.1

    # Check event emissions (2 progress events + 1 complete event = 3 total)
    assert mock_event_bus.emit.call_count == 3

    events = [call[0][0] for call in mock_event_bus.emit.call_args_list]

    # One completion event
    completion_events = [e for e in events if e.is_complete]
    assert len(completion_events) == 1
    assert completion_events[0].total_targets == 2

    # Two progress events
    progress_events = [e for e in events if not e.is_complete]
    assert len(progress_events) == 2

    symbols_emitted = sorted([e.symbol for e in progress_events])
    assert symbols_emitted == ["BTCUSDT", "ETHUSDT"]

    indexes = sorted([e.current_index for e in progress_events])
    assert indexes == [1, 2]


@patch("time.sleep")
def test_bulk_sync_error_handling(mock_sleep, handler, mock_event_bus, mock_dispatcher):
    targets = [("BTCUSDT", "1m"), ("ETHUSDT", "5m")]
    cmd = BulkSyncMarketDataCommand(targets=targets)

    # Simulate an error on one of the syncs
    def side_effect(cmd_type, cmd):
        if cmd.symbols == ["BTCUSDT"]:
            raise _NetworkError("Network Error")

    mock_dispatcher.dispatch.side_effect = side_effect

    handler.execute(cmd)

    # Dispatch was called twice despite the first one failing
    assert mock_dispatcher.dispatch.call_count == 2

    # Events emitted: 1 error progress, 1 success progress, 1 complete = 3 total
    assert mock_event_bus.emit.call_count == 3

    events = [call[0][0] for call in mock_event_bus.emit.call_args_list]

    completion_events = [e for e in events if e.is_complete]
    assert len(completion_events) == 1

    progress_events = [e for e in events if not e.is_complete]
    assert len(progress_events) == 2

    btc_event = next(e for e in progress_events if e.symbol == "BTCUSDT")
    assert btc_event.has_error is True
    assert "Network Error" in btc_event.message

    eth_event = next(e for e in progress_events if e.symbol == "ETHUSDT")
    assert eth_event.has_error is False


def test_bulk_sync_cancellation_stops_dispatching(
    handler, mock_event_bus, mock_dispatcher
):
    targets = [("BTCUSDT", "1m"), ("ETHUSDT", "5m")]
    cmd = BulkSyncMarketDataCommand(
        targets=targets,
        cancellation_requested=lambda: True,
    )

    handler.execute(cmd)

    # When cancellation is requested before dispatching, single target aborts without dispatching
    mock_dispatcher.dispatch.assert_not_called()
