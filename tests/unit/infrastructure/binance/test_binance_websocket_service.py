import logging
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)


def test_subscribe_spawns_a_task_for_a_new_owner():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)
    task_manager.spawn.return_value = Mock()

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        result = service.subscribe("trading", ["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert result is True
    assert service._task_handle is task_manager.spawn.return_value
    assert task_manager.spawn.call_count == 1
    call_args = task_manager.spawn.call_args
    assert call_args[1]["name"] == "BinanceStream[BTCUSDT@1m]"
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
        service.subscribe("trading", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", ["ETHUSDT"], TimeFrame.ONE_MINUTE)

    assert task_manager.spawn.call_count == 2
    assert service._subscriptions == {("ETHUSDT", "1m"): {"trading"}}


def test_second_owner_on_the_same_key_does_not_restart_the_task():
    """Locks the one case that must NOT pay the reconnect price: a second
    owner joining a key another owner already holds."""
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)
    first_handle = Mock()
    task_manager.spawn.return_value = first_handle

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("dashboard", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", ["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert task_manager.spawn.call_count == 1
    assert first_handle.cancel.call_count == 0
    assert service._task_handle is first_handle
    assert service._subscriptions == {("BTCUSDT", "1m"): {"dashboard", "trading"}}


def test_release_owner_keeps_the_other_owners_key_alive():
    """The exact scenario this task exists to fix: one screen releasing its
    own subscription must never stop another screen's stream."""
    event_bus = Mock()
    task_manager = Mock()
    handles = [Mock(name="first"), Mock(name="second")]
    task_manager.spawn.side_effect = handles
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("dashboard", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        result = service.release_owner("dashboard")

    assert result is True
    # Same key set before/after ("trading" alone still needs BTCUSDT@1m) ->
    # no restart, "trading" never loses a tick over "dashboard" leaving.
    assert task_manager.spawn.call_count == 1
    assert handles[0].cancel.call_count == 0
    assert service._subscriptions == {("BTCUSDT", "1m"): {"trading"}}


def test_release_owner_stops_the_task_once_no_owner_remains():
    event_bus = Mock()
    task_manager = Mock()
    handle = Mock()
    task_manager.spawn.return_value = handle
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        service.subscribe("trading", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        result = service.release_owner("trading")

    assert result is True
    assert handle.cancel.call_count == 1
    assert service._task_handle is None
    assert service._subscriptions == {}


def test_release_owner_with_nothing_running_is_a_no_op():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.logger"
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
        service.subscribe("dashboard", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        service.subscribe("trading", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
        result = service.stop_all()

    assert result is True
    assert handle.cancel.call_count == 1
    assert service._task_handle is None
    assert service._subscriptions == {}


def test_stop_all_with_nothing_running_is_a_no_op():
    service = BinanceWebsocketService(Mock(), Mock())
    assert service.stop_all() is False


def test_create_socket_uses_plain_kline_socket_for_a_single_key():
    """A single (symbol, interval) key should use the plain kline_socket,
    not the multiplex one."""
    bsm = Mock()

    socket = BinanceWebsocketService._create_socket(
        bsm, [("BTCUSDT", "1m")], ["btcusdt@kline_1m"]
    )

    bsm.kline_socket.assert_called_once_with("BTCUSDT", interval="1m")
    bsm.multiplex_socket.assert_not_called()
    assert socket is bsm.kline_socket.return_value


def test_create_socket_uses_multiplex_socket_for_multiple_keys():
    bsm = Mock()
    streams = ["btcusdt@kline_1m", "ethusdt@kline_5m"]

    socket = BinanceWebsocketService._create_socket(
        bsm, [("BTCUSDT", "1m"), ("ETHUSDT", "5m")], streams
    )

    bsm.multiplex_socket.assert_called_once_with(streams)
    bsm.kline_socket.assert_not_called()
    assert socket is bsm.multiplex_socket.return_value


@pytest.mark.asyncio
async def test_process_socket_message_ignores_empty_message():
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    async def mock_recv():
        return None

    tscm.recv = mock_recv

    await service._process_socket_message(tscm)

    event_bus.emit.assert_not_called()


@pytest.mark.asyncio
async def test_process_socket_message_ignores_non_kline_events():
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    async def mock_recv():
        return {"e": "trade"}

    tscm.recv = mock_recv

    await service._process_socket_message(tscm)

    event_bus.emit.assert_not_called()


@pytest.mark.asyncio
async def test_process_socket_message_unwraps_multiplex_envelope_and_emits():
    """Multiplex streams wrap the real payload in a top-level "data" key."""
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    async def mock_recv():
        return {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                "k": {
                    "s": "BTCUSDT",
                    "i": "1m",
                    "t": 0,
                    "T": 0,
                    "o": "1",
                    "h": "1",
                    "l": "1",
                    "c": "1",
                    "v": "1",
                    "q": "1",
                    "n": 1,
                    "V": "1",
                    "Q": "1",
                    "x": True,
                },
            },
        }

    tscm.recv = mock_recv

    await service._process_socket_message(tscm)

    assert event_bus.emit.call_count == 1
    emitted_event = event_bus.emit.call_args[0][0]
    assert emitted_event.market_data.symbol == "BTCUSDT"
    assert emitted_event.market_data.is_closed is True


@pytest.mark.asyncio
async def test_kline_tick_logs_at_debug_not_info(caplog) -> None:
    """`BUG-113` (`BUG-042`/`BUG-095` regression) — every kline WebSocket
    message fires this line, several times a second on an active symbol;
    at `INFO` it is exactly the per-event flood `logging-rule.md` §4/§6
    forbid at that level and `BUG-042` once froze the UI with, reported
    directly by a user reading their own real session log."""
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    async def mock_recv():
        return {
            "e": "kline",
            "k": {
                "s": "BTCUSDT",
                "i": "1m",
                "t": 0,
                "T": 0,
                "o": "1",
                "h": "1",
                "l": "1",
                "c": "1",
                "v": "1",
                "q": "1",
                "n": 1,
                "V": "1",
                "Q": "1",
                "x": False,
            },
        }

    tscm.recv = mock_recv

    with caplog.at_level(logging.DEBUG, logger="App.LiveStream"):
        await service._process_socket_message(tscm)

    assert any(
        "[Live Stream]" in record.message and record.levelno == logging.DEBUG
        for record in caplog.records
    )
    assert not any(
        "[Live Stream]" in record.message and record.levelno >= logging.INFO
        for record in caplog.records
    )


def test_parse_kline():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)

    mock_payload = {
        "e": "kline",
        "E": 123456789,
        "s": "BTCUSDT",
        "k": {
            "t": 123400000,
            "T": 123460000,
            "s": "BTCUSDT",
            "i": "1m",
            "f": 100,
            "L": 200,
            "o": "0.0010",
            "c": "0.0020",
            "h": "0.0025",
            "l": "0.0015",
            "v": "1000",
            "n": 100,
            "x": False,  # Not closed yet
            "q": "1.0000",
            "V": "500",
            "Q": "0.500",
            "B": "123456",
        },
    }

    market_data = service._parse_kline(mock_payload)

    assert market_data.symbol == "BTCUSDT"
    assert market_data.interval == "1m"
    assert market_data.open_price == 0.0010
    assert market_data.close_price == 0.0020
    assert market_data.high_price == 0.0025
    assert market_data.low_price == 0.0015
    assert market_data.volume == 1000.0
    assert market_data.is_closed is False

    # Test a closed candle
    mock_payload["k"]["x"] = True
    market_data_closed = service._parse_kline(mock_payload)
    assert market_data_closed.is_closed is True


@pytest.mark.asyncio
async def test_websocket_auto_reconnect():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)

    token = Mock()
    is_cancelled_flag = False

    def check_cancelled():
        return is_cancelled_flag

    token.is_cancelled.side_effect = check_cancelled

    class FakeSocket:
        def __init__(self):
            self.recv_calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def recv(self):
            nonlocal is_cancelled_flag
            self.recv_calls += 1
            if self.recv_calls == 1:
                raise OSError("Network Dropped")
            if self.recv_calls == 2:
                return {
                    "e": "kline",
                    "k": {
                        "s": "BTCUSDT",
                        "i": "1m",
                        "t": 0,
                        "T": 0,
                        "o": 0,
                        "h": 0,
                        "l": 0,
                        "c": 0,
                        "v": 0,
                        "q": 0,
                        "n": 0,
                        "V": 0,
                        "Q": 0,
                        "x": False,
                    },
                }
            is_cancelled_flag = True
            return None

    mock_socket = FakeSocket()
    mock_bsm = Mock()
    mock_bsm.kline_socket.return_value = mock_socket

    async def mock_create(**_kwargs):
        return Mock()

    async def mock_close_connection():
        return None

    async def mock_sleep_coro(*args, **kwargs):
        return None

    mock_client = Mock()
    mock_client.close_connection = mock_close_connection
    mock_async_client = Mock()
    mock_async_client.create = mock_create

    with (
        patch("asyncio.sleep", new=mock_sleep_coro),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient",
            mock_async_client,
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ) as mock_bsm_class,
    ):
        mock_bsm_class.return_value = mock_bsm
        await service._run_stream([("BTCUSDT", "1m")], token)

    assert mock_bsm.kline_socket.call_count >= 2
    assert event_bus.emit.call_count == 1


@pytest.mark.asyncio
async def test_process_socket_message_handles_parsing_exceptions_gracefully():
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    # Missing 'k' key in kline message
    async def mock_recv_missing_k():
        return {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                # "k": {} is missing
            },
        }

    tscm.recv = mock_recv_missing_k

    with patch(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.logger"
    ) as mock_logger:
        await service._process_socket_message(tscm)

        # Event should not be emitted due to parsing exception
        event_bus.emit.assert_not_called()

        # Logger should log the error
        mock_logger.error.assert_called_once()
        log_args = mock_logger.error.call_args[0][0]
        assert "Error parsing kline message" in log_args

    # Malformed data type (e.g. string where number is expected)
    async def mock_recv_invalid_timestamp():
        return {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                "k": {
                    "s": "BTCUSDT",
                    "i": "1m",
                    "t": "INVALID_TIMESTAMP",
                    "T": 0,
                    "o": "1",
                    "h": "1",
                    "l": "1",
                    "c": "1",
                    "v": "1",
                    "q": "1",
                    "n": 1,
                    "V": "1",
                    "Q": "1",
                    "x": True,
                },
            },
        }

    tscm.recv = mock_recv_invalid_timestamp

    with patch(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.logger"
    ) as mock_logger:
        await service._process_socket_message(tscm)

        # Event should not be emitted due to parsing exception
        event_bus.emit.assert_not_called()

        # Logger should log the error
        mock_logger.error.assert_called_once()
        log_args = mock_logger.error.call_args[0][0]
        assert "Error parsing kline message" in log_args
