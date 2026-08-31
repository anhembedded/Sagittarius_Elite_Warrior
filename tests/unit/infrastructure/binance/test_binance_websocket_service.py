from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)


def test_start_stream_success():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)
    task_manager.spawn.return_value = Mock()

    with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
        result = service.start_stream(["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert result is True
    assert service._task_handle is task_manager.spawn.return_value
    assert service._token is not None
    assert task_manager.spawn.call_count == 1
    call_args = task_manager.spawn.call_args
    assert call_args[1]["name"] == "BinanceStream[BTCUSDT@1m]"
    assert call_args[1]["token"] == service._token
    assert call_args[1]["critical"] is True


def test_start_stream_already_running():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)
    service._task_handle = Mock()

    with patch(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.logger"
    ) as mock_logger:
        result = service.start_stream(["BTCUSDT"], TimeFrame.ONE_MINUTE)

    assert result is False
    assert task_manager.spawn.call_count == 0
    mock_logger.warning.assert_called_once_with(
        "Stream is already running. Stop it first."
    )


def test_stop_stream_success():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)

    mock_token = Mock()
    mock_task_handle = Mock()

    service._token = mock_token
    service._task_handle = mock_task_handle

    result = service.stop_stream()

    assert result is True
    assert mock_token.cancel.call_count == 1
    assert mock_task_handle.cancel.call_count == 1
    assert service._task_handle is None
    assert service._token is None


def test_stop_stream_not_running():
    event_bus = Mock()
    task_manager = Mock()
    service = BinanceWebsocketService(event_bus, task_manager)

    with patch(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.logger"
    ) as mock_logger:
        result = service.stop_stream()

    assert result is False
    # Dừng khi chưa chạy là trạng thái bình thường -> DEBUG, không WARNING.
    # Trước đây là WARNING và nó nổ mỗi lần app tắt mà không mở stream, đủ làm
    # đỏ bước "Run Log Scan" của gate.
    mock_logger.warning.assert_not_called()
    assert mock_logger.debug.called


def test_create_socket_uses_plain_kline_socket_for_a_single_symbol():
    """A single symbol should use the plain kline_socket, not the multiplex one."""
    service = BinanceWebsocketService(Mock(), Mock())
    bsm = Mock()
    interval = TimeFrame.ONE_MINUTE

    socket = service._create_socket(bsm, ["BTCUSDT"], ["btcusdt@kline_1m"], interval)

    bsm.kline_socket.assert_called_once_with("BTCUSDT", interval="1m")
    bsm.multiplex_socket.assert_not_called()
    assert socket is bsm.kline_socket.return_value


def test_create_socket_uses_multiplex_socket_for_multiple_symbols():
    service = BinanceWebsocketService(Mock(), Mock())
    bsm = Mock()
    streams = ["btcusdt@kline_1m", "ethusdt@kline_1m"]

    socket = service._create_socket(
        bsm, ["BTCUSDT", "ETHUSDT"], streams, TimeFrame.ONE_MINUTE
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

    async def mock_create():
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
        await service._run_stream(["BTCUSDT"], TimeFrame("1m"), token)

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
