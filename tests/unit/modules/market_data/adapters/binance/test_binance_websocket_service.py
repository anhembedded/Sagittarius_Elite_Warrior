import logging
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service import (
    BinanceWebsocketService,
)

_SPOT = MarketType.SPOT
_FUTURES = MarketType.FUTURES_USD_M


@pytest.mark.asyncio
async def test_process_socket_message_ignores_empty_message():
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    async def mock_recv():
        return None

    tscm.recv = mock_recv

    await service._process_socket_message(tscm, _SPOT)

    event_bus.emit.assert_not_called()


@pytest.mark.asyncio
async def test_process_socket_message_ignores_non_kline_events():
    event_bus = Mock()
    service = BinanceWebsocketService(event_bus, Mock())
    tscm = Mock()

    async def mock_recv():
        return {"e": "trade"}

    tscm.recv = mock_recv

    await service._process_socket_message(tscm, _SPOT)

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

    await service._process_socket_message(tscm, _SPOT)

    assert event_bus.emit.call_count == 1
    emitted_event = event_bus.emit.call_args[0][0]
    assert emitted_event.market_data.symbol == "BTCUSDT"
    assert emitted_event.market_data.is_closed is True
    assert emitted_event.market_type is _SPOT


@pytest.mark.asyncio
async def test_a_tick_is_labelled_with_the_market_its_connection_streams():
    """The same `BTCUSDT@1m` payload read off the Futures connection is a
    Futures candle: the label comes from the connection, never guessed from
    the symbol."""
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
                "x": True,
            },
        }

    tscm.recv = mock_recv

    await service._process_socket_message(tscm, _FUTURES)

    assert event_bus.emit.call_args[0][0].market_type is _FUTURES


@pytest.mark.asyncio
async def test_kline_tick_logs_at_trace_only(caplog) -> None:
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
        await service._process_socket_message(tscm, _SPOT)
    # `BUG-163` (`logging-rule.md` §6): per-tick is `TRACE`, never `DEBUG`
    # either — a `--dev` log held two lines per tick per symbol.
    assert not any("[Live Stream]" in r.message for r in caplog.records)

    caplog.clear()
    with caplog.at_level(5, logger="App.LiveStream"):
        await service._process_socket_message(tscm, _SPOT)
    (record,) = [r for r in caplog.records if "[Live Stream]" in r.message]
    assert record.levelno == 5


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
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.AsyncClient",
            mock_async_client,
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.BinanceSocketManager"
        ) as mock_bsm_class,
    ):
        mock_bsm_class.return_value = mock_bsm
        await service._run_stream(_SPOT, [("BTCUSDT", "1m")], token)

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
        "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.logger"
    ) as mock_logger:
        await service._process_socket_message(tscm, _SPOT)

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
        "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.logger"
    ) as mock_logger:
        await service._process_socket_message(tscm, _SPOT)

        # Event should not be emitted due to parsing exception
        event_bus.emit.assert_not_called()

        # Logger should log the error
        mock_logger.error.assert_called_once()
        log_args = mock_logger.error.call_args[0][0]
        assert "Error parsing kline message" in log_args
