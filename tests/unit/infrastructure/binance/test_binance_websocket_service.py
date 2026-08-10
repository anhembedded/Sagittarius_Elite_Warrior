from unittest.mock import AsyncMock, Mock, patch

import pytest
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)


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
    tscm.recv = AsyncMock(return_value=None)

    await service._process_socket_message(tscm)

    event_bus.emit.assert_not_called()


@pytest.mark.asyncio
async def test_process_socket_message_ignores_non_kline_events():
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()
    tscm.recv = AsyncMock(return_value={"e": "trade"})

    await service._process_socket_message(tscm)

    event_bus.emit.assert_not_called()


@pytest.mark.asyncio
async def test_process_socket_message_unwraps_multiplex_envelope_and_emits():
    """Multiplex streams wrap the real payload in a top-level "data" key."""
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()
    tscm.recv = AsyncMock(
        return_value={
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
    )

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

    # Mock AsyncClient and BinanceSocketManager
    mock_bsm = Mock()
    service._bsm = mock_bsm

    mock_socket = Mock()

    async def mock_aenter(self):
        return self

    async def mock_aexit(self, exc_type, exc, tb):
        pass

    mock_socket.__aenter__ = mock_aenter
    mock_socket.__aexit__ = mock_aexit

    # First recv raises Exception (network error)
    # Second recv returns data (reconnected)
    # Third recv cancels the task to stop the infinite loop
    call_count = 0

    async def mock_recv():
        nonlocal call_count, is_cancelled_flag
        call_count += 1
        if call_count == 1:
            raise OSError("Network Dropped")
        elif call_count == 2:
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
        else:
            is_cancelled_flag = True  # break the loop
            return None

    mock_socket.recv = mock_recv
    mock_bsm.kline_socket.return_value = mock_socket

    # We patch asyncio.sleep so we don't actually wait 5 seconds in the test
    with (
        patch("asyncio.sleep", new_callable=Mock) as mock_sleep,
        patch(
            "Binace_Bot.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ) as mock_async_client,
        patch(
            "Binace_Bot.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ) as mock_bsm_class,
    ):
        # Mock AsyncClient.create to return a mock client
        mock_client = Mock()

        async def mock_create():
            return mock_client

        async def mock_close_connection():
            pass

        mock_client.close_connection.side_effect = mock_close_connection
        mock_async_client.create.side_effect = mock_create

        # Mock BinanceSocketManager to return our mock_bsm
        mock_bsm_class.return_value = mock_bsm

        # mock_sleep must return a coroutine
        async def mock_sleep_coro(*args, **kwargs):
            pass

        mock_sleep.side_effect = mock_sleep_coro

        await service._run_stream(["BTCUSDT"], TimeFrame("1m"), token)

    # Assertions
    # It should have called kline_socket at least twice (initial + 1 reconnect)
    assert mock_bsm.kline_socket.call_count >= 2
    # It should have emitted the event for the second successful recv
    assert event_bus.emit.call_count == 1


@pytest.mark.asyncio
async def test_process_socket_message_handles_parsing_exceptions_gracefully():
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    # Missing 'k' key in kline message
    tscm.recv = AsyncMock(
        return_value={
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                # "k": {} is missing
            },
        }
    )

    with patch(
        "Binace_Bot.src.infrastructure.binance.binance_websocket_service.logger"
    ) as mock_logger:
        await service._process_socket_message(tscm)

        # Event should not be emitted due to parsing exception
        event_bus.emit.assert_not_called()

        # Logger should log the error
        mock_logger.error.assert_called_once()
        log_args = mock_logger.error.call_args[0][0]
        assert "Error parsing kline message" in log_args

    # Malformed data type (e.g. string where number is expected)
    tscm.recv = AsyncMock(
        return_value={
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
    )

    with patch(
        "Binace_Bot.src.infrastructure.binance.binance_websocket_service.logger"
    ) as mock_logger:
        await service._process_socket_message(tscm)

        # Event should not be emitted due to parsing exception
        event_bus.emit.assert_not_called()

        # Logger should log the error
        mock_logger.error.assert_called_once()
        log_args = mock_logger.error.call_args[0][0]
        assert "Error parsing kline message" in log_args
