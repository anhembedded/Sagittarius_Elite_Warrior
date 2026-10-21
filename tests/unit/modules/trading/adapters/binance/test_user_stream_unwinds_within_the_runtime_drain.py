"""`BUG-143` — stopping the app with a user-data stream live must not outlast
`AsyncRuntime`'s drain (5 s in the app: `App.stop` gives the runtime 10 s and
the drain takes half).

The owner's Spot Mainnet run printed, at close, `1 task(s) did not finish
cancelling within 5.0s ... SpotUserDataStream` and `async generators did not
close within 5.0s`, and none of the stream's own lines. `AsyncRuntime.stop()`
cancels every task at once, the `ws_api` read loop included; the Spot socket's
exit then sends `userDataStream.unsubscribe` and waits the library's 10 s for a
reply that read loop can no longer deliver. Separately, closing a client or a
socket whose read loop is alive but idle waits for that loop's current receive,
also up to 10 s, which shows when one stream is stopped while the loop runs.

These tests use the library's real `AsyncClient`, `BinanceSocketManager`,
`KeepAliveWebsocket` and `ReconnectingWebsocket` over a loopback peer that
answers requests and pushes nothing (`quiet_loopback_exchange.py`); only the
client's construction (which would reach Binance) is replaced.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from unittest.mock import Mock, patch

import pytest
from binance import AsyncClient
from binance.ws.reconnecting_websocket import ReconnectingWebsocket
from binance.ws.websocket_api import WebsocketAPI
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.asyncio_task_manager import (
    AsyncioTaskManager,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.emitter_builder import (
    venue_emitter,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.quiet_loopback_exchange import (
    quiet_loopback_exchange,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.runtime.async_runtime.async_runtime import AsyncRuntime
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

_TRADING = "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance."
_SPOT = _TRADING + "spot.spot_user_data_stream"
_FUTURES = _TRADING + "futures_user_data_stream"

#: The stream must be over well inside the runtime's 5 s drain; the library's
#: own wait is 10 s, so this separates the two with room on both sides.
_UNWIND_SECONDS = 3.0
_LIBRARY_WAIT_SECONDS = 15.0


def _credentials() -> Mock:
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"), CredentialsSource.FILE
    )
    return provider


def _spot_stream(tasks: ITaskManager) -> tuple[SpotUserDataStream, threading.Event]:
    """A Spot stream and the event set once it reports `CONNECTED`."""
    bus = MemoryEventBus()
    connected = threading.Event()

    def on_health(event: UserStreamHealthEvent) -> None:
        if event.state is UserStreamState.CONNECTED:
            connected.set()

    bus.on(UserStreamHealthEvent, on_health)
    stream = SpotUserDataStream(
        venue_emitter(bus, TradingVenue.SPOT_TESTNET),
        tasks,
        _credentials(),
        FakeTradingAccountReader(),
        EquityCurveRecorder(),
    )
    return stream, connected


def _client_on(url: str) -> AsyncClient:
    """A real `AsyncClient` whose `ws_api` is the loopback exchange. Its
    constructor reaches no network; `AsyncClient.create` would."""
    client = AsyncClient(api_key="key", api_secret="secret")
    client.ws_api = WebsocketAPI(url=url)
    return client


def _creating(client: AsyncClient) -> Callable[..., Awaitable[AsyncClient]]:
    async def create(**_kwargs: object) -> AsyncClient:
        return client

    return create


class _IdleFuturesSocket(ReconnectingWebsocket):
    """What `bsm.futures_user_socket()` returns, minus the listen key: the
    library's real socket, connected to the loopback exchange."""

    def __init__(self, url: str, entered: asyncio.Event) -> None:
        super().__init__(url=url, path="", prefix="")
        self._entered = entered

    async def connect(self) -> None:
        await super().connect()
        self._entered.set()


@pytest.fixture
async def silent_exchange() -> AsyncIterator[str]:
    async with quiet_loopback_exchange() as url:
        yield url


async def _cancel_like_the_runtime_drain(task: asyncio.Task[None]) -> bool:
    """Cancel `task` once, as `AsyncRuntime._drain` does, and say whether it
    finished within `_UNWIND_SECONDS`."""
    task.cancel()
    done, _pending = await asyncio.wait({task}, timeout=_UNWIND_SECONDS)
    if task not in done:
        await asyncio.wait({task}, timeout=_LIBRARY_WAIT_SECONDS)
    return task in done


async def _spot_stream_task_cancelled_alone(
    url: str,
) -> tuple[bool, asyncio.Task[None], AsyncClient]:
    client = _client_on(url)
    tasks = AsyncioTaskManager()
    stream, connected = _spot_stream(tasks)
    with patch(f"{_SPOT}.AsyncClient") as async_client:
        async_client.create = _creating(client)
        assert stream.start()
        task = tasks.handles[0].task
        assert await asyncio.to_thread(connected.wait, _UNWIND_SECONDS)
        unwound = await _cancel_like_the_runtime_drain(task)
    return unwound, task, client


async def test_spot_stream_over_an_idle_connection_unwinds_within_the_drain(
    silent_exchange: str, caplog: pytest.LogCaptureFixture
) -> None:
    """One stream stopped while the loop keeps running: its `ws_api` read loop
    is alive and idle, and the client's close must not wait for it."""
    with caplog.at_level(logging.INFO, logger="App"):
        unwound, _task, client = await _spot_stream_task_cancelled_alone(
            silent_exchange
        )

    assert unwound, "the task was still closing the client when the drain gave up"
    assert client.ws_api.ws is None, "the connection was closed, not abandoned"
    assert any(
        "AsyncClient connection closed" in record.getMessage()
        for record in caplog.records
    ), "the close completed rather than being abandoned"


async def test_cancelling_a_stream_ends_its_task_as_cancelled(
    silent_exchange: str,
) -> None:
    """Cancellation propagates: the supervisor logs it and re-raises, so the
    task ends `cancelled()` for whoever awaits it, not as a normal return."""
    unwound, task, _client = await _spot_stream_task_cancelled_alone(silent_exchange)

    assert unwound
    assert task.cancelled()


async def test_futures_stream_over_an_idle_connection_unwinds_within_the_drain(
    silent_exchange: str,
) -> None:
    entered = asyncio.Event()
    socket = _IdleFuturesSocket(silent_exchange, entered)
    bsm = Mock()
    bsm.futures_user_socket.side_effect = lambda: socket
    tasks = AsyncioTaskManager()
    stream = FuturesUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.FUTURES_TESTNET),
        tasks,
        _credentials(),
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )

    client = _client_on(silent_exchange)
    with (
        patch(f"{_FUTURES}.AsyncClient") as async_client,
        patch(f"{_FUTURES}.BinanceSocketManager", return_value=bsm),
    ):
        async_client.create = _creating(client)
        assert stream.start()
        task = tasks.handles[0].task
        await asyncio.wait_for(entered.wait(), timeout=_UNWIND_SECONDS)
        unwound = await _cancel_like_the_runtime_drain(task)

    assert unwound, "the task was still inside the library's socket close"
    assert socket.ws is None, "the socket was closed, not abandoned"
    assert client.session.closed, (
        "the HTTP session was closed (`Unclosed client session`)"
    )


def test_stopping_the_runtime_with_the_spot_stream_live_prints_no_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The owner's check, end to end: the real `AsyncRuntime.stop()` (the
    10 s step `App.stop()` gives it, so a 5 s drain) over the stream task on
    the runtime's own loop. `did not finish cancelling` and `async generators
    did not close` must not be logged, nor any other WARNING."""
    runtime = AsyncRuntime(Mock())
    stream, connected = _spot_stream(AsyncioTaskManager())
    stream._generation = 1

    async def stream_over_an_idle_connection() -> None:
        async with quiet_loopback_exchange() as url:
            with patch(f"{_SPOT}.AsyncClient") as async_client:
                async_client.create = _creating(_client_on(url))
                await stream._run_stream(CancellationToken(), generation=1)

    with caplog.at_level(logging.INFO):
        runtime.start()
        running = runtime.run_coroutine(stream_over_an_idle_connection())
        assert connected.wait(timeout=_UNWIND_SECONDS), "the stream connected"
        runtime.stop(timeout=10.0)

    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == []
    assert running.done()
    assert runtime.loop is None, "the loop was stopped and closed"
