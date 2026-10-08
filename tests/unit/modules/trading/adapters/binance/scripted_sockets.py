"""Scripted `python-binance` sockets for the user-data stream tests.

`FAILURES` are the failure modes `python-binance==1.0.37` raises out of
`async with bsm.user_socket()` / `stream.recv()` (`ws/keepalive_websocket.py`,
`ws/reconnecting_websocket.py`, `exceptions.py`), plus one nobody listed: a
stream must not care which. `Socket` is one `async with` over such a socket.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Self
from unittest.mock import Mock

from binance.exceptions import (
    BinanceAPIException,
    BinanceWebsocketUnableToConnect,
    ReadLoopClosed,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


def api_error() -> BinanceAPIException:
    response = Mock(status_code=400, text='{"code": -1021, "msg": "Timestamp ahead"}')
    return BinanceAPIException(response, 400, response.text)


#: The failures `python-binance==1.0.37` raises out of `async with socket` /
#: `stream.recv()`, plus one nobody listed: the stream must not care which.
FAILURES: list[Exception] = [
    ValueError("Failed to subscribe to user data stream: no subscription ID returned"),
    BinanceWebsocketUnableToConnect(),
    api_error(),
    ReadLoopClosed("Read loop has been closed"),
    ConnectionResetError("reset by peer"),
    RuntimeError("anything else"),
]


class Socket:
    """One `async with bsm.user_socket()`: fails on entry, fails on `recv`, or
    runs `on_recv` (which may cancel the token to end the stream)."""

    def __init__(
        self,
        enter_error: Exception | None = None,
        recv_error: Exception | None = None,
        on_recv: Callable[[], Awaitable[None] | None] | None = None,
    ) -> None:
        self._enter_error = enter_error
        self._recv_error = recv_error
        self._on_recv = on_recv

    async def __aenter__(self) -> Self:
        if self._enter_error is not None:
            raise self._enter_error
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    async def recv(self) -> dict[str, str] | None:
        if self._recv_error is not None:
            raise self._recv_error
        if self._on_recv is not None:
            result = self._on_recv()
            if result is not None:
                await result
        return None


def fail(error: Exception, *, at_enter: bool) -> Socket:
    if at_enter:
        return Socket(enter_error=error)
    return Socket(recv_error=error)


def ends_the_stream(token: CancellationToken) -> Socket:
    """A socket whose first `recv` cancels the token: the stream then ends."""
    return Socket(on_recv=token.cancel)
