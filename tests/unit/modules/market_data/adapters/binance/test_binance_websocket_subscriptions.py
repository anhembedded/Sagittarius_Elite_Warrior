"""`BinanceWebsocketService`: subscription bookkeeping per owner and per market.

Split from `test_binance_websocket_service.py` (`BOT-146`), which keeps the
message processing, parsing and reconnect tests.
"""

from unittest.mock import Mock, patch

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service import (
    BinanceWebsocketService,
)

_SPOT = MarketType.SPOT
_FUTURES = MarketType.FUTURES_USD_M


def test_subscribe_spawns_a_task_for_a_new_owner():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)
    task_manager.spawn.return_value = Mock()

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        result = service.subscribe("trading", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert result is True
    assert service._running[_SPOT].handle is task_manager.spawn.return_value
    assert task_manager.spawn.call_count == 1
    call_args = task_manager.spawn.call_args
    assert call_args[1]["name"] == "BinanceStream[spot:BTCUSDT@1m]"
    assert call_args[1]["critical"] is True


def test_subscribe_replaces_the_same_owners_previous_subscription():
    """`BOT-126` — a screen calling `subscribe()` again (symbol/interval
    change) must not need to `release_owner()` first: the new call replaces
    its own old set outright."""
    event_bus = Mock()
    task_manager = Mock()
    task_manager.spawn.side_effect = [Mock(name="first"), Mock(name="second")]
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("trading", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", _SPOT, ["ETHUSDT"], TimeFrame.ONE_MINUTE)

    assert task_manager.spawn.call_count == 2
    assert service._subscriptions == {(_SPOT, "ETHUSDT", "1m"): {"trading"}}


def test_second_owner_on_the_same_key_does_not_restart_the_task():
    """Locks the one case that must NOT pay the reconnect price: a second
    owner joining a key another owner already holds."""
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)
    first_handle = Mock()
    task_manager.spawn.return_value = first_handle

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("dashboard", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert task_manager.spawn.call_count == 1
    assert first_handle.cancel.call_count == 0
    assert service._running[_SPOT].handle is first_handle
    assert service._subscriptions == {
        (_SPOT, "BTCUSDT", "1m"): {"dashboard", "trading"}
    }


def test_release_owner_keeps_the_other_owners_key_alive():
    """The exact scenario this task exists to fix: one screen releasing its
    own subscription must never stop another screen's stream."""
    event_bus = Mock()
    task_manager = Mock()
    handles = [Mock(name="first"), Mock(name="second")]
    task_manager.spawn.side_effect = handles
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("dashboard", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        result = service.release_owner("dashboard")

    assert result is True
    # Same key set before/after ("trading" alone still needs BTCUSDT@1m) ->
    # no restart, "trading" never loses a tick over "dashboard" leaving.
    assert task_manager.spawn.call_count == 1
    assert handles[0].cancel.call_count == 0
    assert service._subscriptions == {(_SPOT, "BTCUSDT", "1m"): {"trading"}}


def test_release_owner_stops_the_task_once_no_owner_remains():
    event_bus = Mock()
    task_manager = Mock()
    handle = Mock()
    task_manager.spawn.return_value = handle
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("trading", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        result = service.release_owner("trading")

    assert result is True
    assert handle.cancel.call_count == 1
    assert service._running == {}
    assert service._subscriptions == {}


def test_release_owner_with_nothing_running_is_a_no_op():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.logger"
    ) as mock_logger:
        result = service.release_owner("trading")

    assert result is False
    assert task_manager.spawn.call_count == 0
    # Dừng khi chưa chạy là trạng thái bình thường -> DEBUG, không WARNING.
    mock_logger.warning.assert_not_called()
    assert mock_logger.debug.called


def test_stop_all_tears_down_regardless_of_owner():
    event_bus = Mock()
    task_manager = Mock()
    handle = Mock()
    task_manager.spawn.return_value = handle
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        # Same key for both owners -> exactly one spawn, so `handle.cancel`
        # below can only be `stop_all()`'s own teardown, not an earlier
        # subscribe-triggered restart reusing the same mock return value.
        service.subscribe("dashboard", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        result = service.stop_all()

    assert result is True
    assert handle.cancel.call_count == 1
    assert service._running == {}
    assert service._subscriptions == {}


def test_stop_all_with_nothing_running_is_a_no_op():
    service = BinanceWebsocketService(Mock(), Mock())
    assert service.stop_all() is False


def test_each_market_gets_its_own_connection():
    """`EPIC-028C` — Spot and Futures klines come from two hosts, so the
    Futures desk's `BTCUSDT@1m` is a second connection, not a key on
    Spot's."""
    task_manager = Mock()
    task_manager.spawn.side_effect = [Mock(name="spot"), Mock(name="futures")]
    service = BinanceWebsocketService(Mock(), task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("spot-desk", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("futures-desk", _FUTURES, ["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert set(service._running) == {_SPOT, _FUTURES}
    assert [call[1]["name"] for call in task_manager.spawn.call_args_list] == [
        "BinanceStream[spot:BTCUSDT@1m]",
        "BinanceStream[futures_usd_m:BTCUSDT@1m]",
    ]


def test_a_change_on_one_market_leaves_the_other_markets_connection_alone():
    """The Spot desk changing symbol reconnects Spot only: the Futures
    strategy keeps receiving its candles through the change."""
    task_manager = Mock()
    futures_handle = Mock(name="futures")
    task_manager.spawn.side_effect = [futures_handle, Mock(name="spot"), Mock()]
    service = BinanceWebsocketService(Mock(), task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("futures-desk", _FUTURES, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("spot-desk", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("spot-desk", _SPOT, ["ETHUSDT"], TimeFrame.ONE_MINUTE)
        service.release_owner("spot-desk")

    assert futures_handle.cancel.call_count == 0
    assert service._running[_FUTURES].handle is futures_handle
    assert set(service._running) == {_FUTURES}


def test_an_owner_moving_market_releases_the_market_it_left():
    """Replace, never add, holds across markets too: a screen switched from
    Spot to Futures stops holding Spot's stream open."""
    task_manager = Mock()
    spot_handle = Mock(name="spot")
    task_manager.spawn.side_effect = [spot_handle, Mock(name="futures")]
    service = BinanceWebsocketService(Mock(), task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("desk", _SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("desk", _FUTURES, ["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert spot_handle.cancel.call_count == 1
    assert service._subscriptions == {(_FUTURES, "BTCUSDT", "1m"): {"desk"}}
