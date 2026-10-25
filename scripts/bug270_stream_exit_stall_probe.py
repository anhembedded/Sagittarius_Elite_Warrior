"""`BUG-270` - why a dropped kline WebSocket left the app blind for 30 s, and what the overflow was.

Run it (about 45 s, no network, a local server)::

    PYTHONPATH=.. .venv/bin/python scripts/bug270_stream_exit_stall_probe.py

A local server pushes Futures-rate klines (4 a second) and, on its first connection, closes with
1011 after 12 of them, as the owner's mainnet connection did on 2026-10-25. The probe drives the
real `BinanceWebsocketService._run_stream` and the real `python-binance` `ReconnectingWebsocket`
and prints when the app's consumer reads, the peak of the library's queue and the library's records.

@par What it showed (python-binance as pinned in `requirements.lock`, 2026-10-25)
  1. The library reconnects by itself within a second and the server resumes pushing.
  2. The app's consumer gets the library's `{"e": "error"}` message at once, raises
     `KlineStreamError`, and leaves `async with socket`: `ReconnectingWebsocket.__aexit__` sets
     `ws_state = EXITING` and waits for the read loop to end. The read loop was mid-reconnect, and
     `connect()` then sets `ws_state = STREAMING`, which overwrites `EXITING`: the loop never ends.
  3. The consumer is therefore stuck in that exit and reads **nothing** while the library fills its
     queue of 100 messages (25 s at 4 a second). `BinanceWebsocketQueueOverflow` ends the read loop,
     which releases the exit; only then does the app log its error, wait 5 s and reconnect.

So the overflow is a consumer that did not read (it was held in the socket's own shutdown), not a
burst on reconnect; a 35 s stall of the event loop with the same server produced no overflow.

Retire when: the stream leaves the socket without waiting on the library's read loop, or the library
fixes `__aexit__`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import cast

import websockets
from binance.ws.reconnecting_websocket import ReconnectingWebsocket
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from websockets.asyncio.server import ServerConnection

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance import (
    binance_websocket_service as service_module,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

_KLINES_PER_SECOND = 4
_KLINES_BEFORE_THE_DROP = 12
_WATCH_SECONDS = 40
_GAP_SECONDS = 2
_STARTED = time.monotonic()
_KLINE = json.dumps(
    {
        "data": {
            "e": "kline",
            "k": {
                "s": "BNBUSDT",
                "i": "1m",
                "t": 0,
                "T": 1,
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
    }
)


def _say(line: str) -> None:
    sys.stdout.write(line + "\n")


def _at() -> float:
    return round(time.monotonic() - _STARTED, 1)


class _Bus:
    """The event bus the service publishes ticks on: it only notes when they arrive."""

    def __init__(self) -> None:
        self.arrivals: list[float] = []

    def emit(self, event: object) -> None:
        self.arrivals.append(_at())


class _Client:
    async def close_connection(self) -> None:
        return None


class _Server:
    """Pushes klines; its first connection is closed with 1011 after a few."""

    def __init__(self) -> None:
        self.connections = 0

    async def handle(self, connection: ServerConnection) -> None:
        self.connections += 1
        drops = self.connections == 1
        sent = 0
        try:
            while True:
                if drops and sent >= _KLINES_BEFORE_THE_DROP:
                    await connection.close(1011, "keepalive ping timeout")
                    return
                await connection.send(_KLINE)
                sent += 1
                await asyncio.sleep(1 / _KLINES_PER_SECOND)
        except websockets.ConnectionClosed:
            return


async def _probe() -> None:
    server = _Server()
    sockets: list[ReconnectingWebsocket] = []
    async with websockets.serve(server.handle, "127.0.0.1", 0) as running:
        port = running.sockets[0].getsockname()[1]

        def open_socket(*_: object) -> ReconnectingWebsocket:
            socket = ReconnectingWebsocket(
                f"ws://127.0.0.1:{port}/", path="", prefix=""
            )
            sockets.append(socket)
            return socket

        async def create(*_: object, **__: object) -> _Client:
            return _Client()

        setattr(service_module, "create_closing_on_cancel", create)  # noqa: B010
        setattr(service_module, "BinanceSocketManager", lambda _client: None)  # noqa: B010
        setattr(service_module, "open_kline_socket", open_socket)  # noqa: B010
        bus = _Bus()
        # The probe drives `_run_stream` on its own loop, so it needs no task manager.
        service = service_module.BinanceWebsocketService(
            cast(IEventBus, bus),
            cast(ITaskManager, None),
            MarketDataVenue.MAINNET_PUBLIC,
        )
        token = CancellationToken()
        task = asyncio.create_task(
            service._run_stream(MarketType.FUTURES_USD_M, [("BNBUSDT", "1m")], token)
        )
        peak = 0
        for _ in range(_WATCH_SECONDS * 20):
            await asyncio.sleep(0.05)
            if sockets:
                peak = max(peak, sockets[-1]._queue.qsize())
        token.cancel()
        task.cancel()
    gaps = [
        (before, after)
        for before, after in zip(bus.arrivals, bus.arrivals[1:], strict=False)
        if after - before > _GAP_SECONDS
    ]
    _say(
        f"klines read: {len(bus.arrivals)}; connections the server saw: {server.connections}"
    )
    _say(f"peak of the library's queue: {peak} (its limit is 100)")
    _say(f"gaps in which the consumer read nothing, as (from, to) seconds: {gaps}")


class _Quiet(logging.Handler):
    """Prints the library's and the service's records with the probe's clock."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(("binance", "App.LiveStream")):
            _say(f"{_at():6} {record.name}: {record.getMessage()}")


def main() -> None:
    logging.getLogger().addHandler(_Quiet())
    logging.getLogger().setLevel(logging.INFO)
    asyncio.run(_probe())


if __name__ == "__main__":
    main()
