from datetime import UTC, datetime
from unittest.mock import Mock, call, patch

import pytest

from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_backtest.command import (
    RunBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_backtest.handler import (
    BacktestState,
    RunBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@pytest.fixture
def repo_mock():
    return Mock()


@pytest.fixture
def event_bus_mock():
    return Mock()


@pytest.fixture
def handler(repo_mock, event_bus_mock):
    state = BacktestState()
    return RunBacktestCommandHandler(repo_mock, event_bus_mock, state)


def create_mock_kline(timestamp: datetime) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
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


def test_run_backtest_handler_emits_events(handler, repo_mock, event_bus_mock):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=UTC)
    klines = [create_mock_kline(dt1), create_mock_kline(dt2)]

    repo_mock.get_klines.return_value = klines

    command = RunBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        limit=2,
        replay_speed_ms=0,  # no sleep to speed up test
    )

    handler.execute(command)

    assert repo_mock.get_klines.called
    assert event_bus_mock.emit.call_count == 2

    first_event = event_bus_mock.emit.call_args_list[0][0][0]
    assert isinstance(first_event, MarketTickEvent)
    assert first_event.market_data.symbol == "BTCUSDT"
    assert first_event.market_data.close_price == 105.0
    assert first_event.market_data.open_time == dt1


@patch("time.sleep")
def test_run_backtest_handler_throttling(
    sleep_mock, handler, repo_mock, event_bus_mock
):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=UTC)
    klines = [create_mock_kline(dt1), create_mock_kline(dt2)]

    repo_mock.get_klines.return_value = klines

    command = RunBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE, limit=2, replay_speed_ms=100
    )

    handler.execute(command)

    # With 2 klines and replay_speed_ms=100, sleep(0.1) should be called twice
    assert sleep_mock.call_count == 2
    sleep_mock.assert_has_calls([call(0.1), call(0.1)])


def test_run_backtest_no_data(handler, repo_mock, event_bus_mock):
    repo_mock.get_klines.return_value = []

    command = RunBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE, limit=10, replay_speed_ms=100
    )

    handler.execute(command)

    # Should exit early without emitting anything
    assert event_bus_mock.emit.call_count == 0
