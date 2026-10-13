"""`BUG-199` — the websocket side of the fake exchange, at the transport.

The fixture used to replace `AsyncClient` and `BinanceSocketManager` with plain
`MagicMock`s. `await AsyncClient.create(...)` on a `MagicMock` raises `TypeError:
object MagicMock can't be used in 'await' expression`, so the first stream a
chart opened failed its task with an ERROR record, and the log scan failed the run
on whichever test it landed in. The same fixture left the trading
user-data-stream modules, which import their own `AsyncClient`, unpatched.

Here `AsyncClient` and `BinanceSocketManager` run unchanged: the first pings the
fake exchange over loopback (`binance_endpoints.py`), the second builds the real
stream names and URLs. Only the two `ReconnectingWebsocket` methods that touch a
socket are replaced: `connect` opens nothing, and `recv` is an exchange that
never sends a message. Every websocket class of the library inherits both, so no
stream, however it is built, can reach a real host.

Retire when: the sanity tier no longer starts live streams.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from binance.ws.constants import WSListenerState
from binance.ws.reconnecting_websocket import ReconnectingWebsocket


class StreamTransport:
    """What the fake transport was asked to open."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._opened: list[str] = []

    def record(self, url: str) -> None:
        with self._lock:
            self._opened.append(url)

    @property
    def opened(self) -> list[str]:
        """Every websocket URL a stream asked to connect to, in order."""
        with self._lock:
            return list(self._opened)


@contextmanager
def fake_websocket_transport() -> Iterator[StreamTransport]:
    transport = StreamTransport()

    async def connect(self: ReconnectingWebsocket) -> None:
        transport.record(f"{self._url}{self._prefix}{self._path}")
        self.ws_state = WSListenerState.STREAMING

    async def recv(self: ReconnectingWebsocket) -> dict[str, object]:
        """A quiet exchange: waits until the stream's task is cancelled."""
        await asyncio.Event().wait()
        raise AssertionError("unreachable: the event is never set")

    with (
        patch.object(ReconnectingWebsocket, "connect", connect),
        patch.object(ReconnectingWebsocket, "recv", recv),
    ):
        yield transport
