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

    # First dispatch call
    call1_type, call1_cmd = mock_dispatcher.dispatch.call_args_list[0][0]
    assert call1_type == SyncMarketDataCommand
    assert isinstance(call1_cmd, SyncMarketDataCommand)
    assert call1_cmd.symbols == ["BTCUSDT"]
    assert call1_cmd.interval.value == "1m"

    # Second dispatch call
    call2_type, call2_cmd = mock_dispatcher.dispatch.call_args_list[1][0]
    assert call2_type == SyncMarketDataCommand
    assert isinstance(call2_cmd, SyncMarketDataCommand)
    assert call2_cmd.symbols == ["ETHUSDT"]
    assert call2_cmd.interval.value == "5m"

    # Check that sleep was called exactly once (between 2 targets)
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(0.1)  # 100ms / 1000

    # Check event emissions (2 progress events + 1 complete event = 3 total)
    assert mock_event_bus.emit.call_count == 3

    evt1 = mock_event_bus.emit.call_args_list[0][0][0]
    assert evt1.current_index == 1
    assert evt1.symbol == "BTCUSDT"

    evt2 = mock_event_bus.emit.call_args_list[1][0][0]
    assert evt2.current_index == 2
    assert evt2.symbol == "ETHUSDT"

    evt3 = mock_event_bus.emit.call_args_list[2][0][0]
    assert evt3.is_complete is True
    assert evt3.total_targets == 2


@patch("time.sleep")
def test_bulk_sync_error_handling(mock_sleep, handler, mock_event_bus, mock_dispatcher):
    targets = [("BTCUSDT", "1m"), ("ETHUSDT", "5m")]
    cmd = BulkSyncMarketDataCommand(targets=targets)

    # Simulate an error on the first sync
    mock_dispatcher.dispatch.side_effect = [Exception("Network Error"), None]

    handler.execute(cmd)

    # Dispatch was called twice despite the first one failing
    assert mock_dispatcher.dispatch.call_count == 2

    # Events emitted: 1 error progress, 1 success progress, 1 complete = 3 total
    assert mock_event_bus.emit.call_count == 3

    evt1 = mock_event_bus.emit.call_args_list[0][0][0]
    assert evt1.current_index == 1
    assert evt1.symbol == "BTCUSDT"
    assert evt1.has_error is True
    assert "Network Error" in evt1.message

    evt2 = mock_event_bus.emit.call_args_list[1][0][0]
    assert evt2.current_index == 2
    assert evt2.symbol == "ETHUSDT"
    assert evt2.has_error is False

    evt3 = mock_event_bus.emit.call_args_list[2][0][0]
    assert evt3.is_complete is True
