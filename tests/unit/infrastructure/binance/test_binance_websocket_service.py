import pytest
from unittest.mock import Mock, patch
from Binace_Bot.src.infrastructure.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


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
