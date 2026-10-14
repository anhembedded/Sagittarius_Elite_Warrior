"""`BUG-209` — the kline stream loop reports every failure it meets and reconnects.

Only `OSError` was caught: any other exception ended the stream task with nothing in the
journal, and the library's own `{"e": "error"}` message fell through as "not a kline".
Split from `test_binance_websocket_service.py` (400-line ceiling).
"""

import logging
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service import (
    BinanceWebsocketService,
)

_SPOT = MarketType.SPOT


_SERVICE_MODULE = (
    "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance."
    "binance_websocket_service"
)


@pytest.mark.asyncio
async def test_an_error_message_from_the_socket_library_is_raised_not_ignored():
    """`BUG-209` — `{"e": "error"}` is how the library reports its own failure; it fell
    through as "not a kline" and the feed went quiet with nothing in the journal."""
    service = BinanceWebsocketService(Mock(), Mock())
    tscm = Mock()

    async def recv():
        return {"e": "error", "type": "BinanceWebsocketClosed", "m": "Max reconnect"}

    tscm.recv = recv

    with pytest.raises(OSError, match="BinanceWebsocketClosed"):
        await service._process_socket_message(tscm, _SPOT)


class _SocketThatBreaksOnce:
    """A kline socket whose first read raises `first`, and whose second ends the run."""

    def __init__(self, first: BaseException, end_run) -> None:
        self._first = first
        self._end_run = end_run
        self._reads = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def recv(self):
        self._reads += 1
        if self._reads == 1:
            raise self._first
        self._end_run()


async def _run_a_stream_whose_first_read_raises(first: BaseException) -> None:
    service = BinanceWebsocketService(Mock(), Mock())
    cancelled = False

    def end_run() -> None:
        nonlocal cancelled
        cancelled = True

    token = Mock()
    token.is_cancelled.side_effect = lambda: cancelled
    bsm = Mock()
    bsm.kline_socket.return_value = _SocketThatBreaksOnce(first, end_run)

    async def create(**_kwargs):
        client = Mock()

        async def close_connection():
            return None

        client.close_connection = close_connection
        return client

    async def no_sleep(*_args, **_kwargs):
        return None

    async_client = Mock()
    async_client.create = create
    with (
        patch("asyncio.sleep", new=no_sleep),
        patch(f"{_SERVICE_MODULE}.AsyncClient", async_client),
        patch(f"{_SERVICE_MODULE}.BinanceSocketManager", return_value=bsm),
    ):
        await service._run_stream(_SPOT, [("BTCUSDT", "1m")], token)
    assert bsm.kline_socket.call_count == 2, "the stream reconnected"


@pytest.mark.asyncio
async def test_an_exception_that_is_not_an_oserror_is_an_error_and_a_reconnect(caplog):
    """`BUG-209` — only `OSError` was caught; anything else ended the stream task
    unlogged, so the bots lost their prices with no ERROR to grep for."""
    with caplog.at_level(logging.DEBUG, logger="App.LiveStream"):
        await _run_a_stream_whose_first_read_raises(RuntimeError("protocol broke"))

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "[kline-stream]" in errors[0].getMessage()
    assert errors[0].exc_info is not None, "the traceback is in the record"
    assert "protocol broke" in caplog.text
