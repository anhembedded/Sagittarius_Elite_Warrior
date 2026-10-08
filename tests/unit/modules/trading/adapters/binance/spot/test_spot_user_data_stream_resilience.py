"""`EPIC-035B` (audit H3) — the Spot user-data stream survives any exception.

Before: `_run_stream` caught `(OSError, ReadLoopClosed)` only, so the library's
`ValueError` ("Failed to subscribe to user data stream", `KeepAliveWebsocket.
_before_connect`), `BinanceWebsocketUnableToConnect` (its reconnect budget of 5
spent), an API error or anything else ended the task for good, and the stale
`_task_handle` made `start()` answer "already running" for ever. The stream is
the only source of fills, so the ladder froze with real orders resting.

The sockets here are scripted from the library's own failure modes, read from
`python-binance==1.0.37` (`ws/keepalive_websocket.py`, `ws/reconnecting_websocket.py`,
`exceptions.py`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.scripted_sockets import (
    FAILURES,
    Socket,
    api_error,
    ends_the_stream,
    fail,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

_MODULE = (
    "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance."
    "spot.spot_user_data_stream"
)


def _credentials() -> Mock:
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"), CredentialsSource.FILE
    )
    return provider


def _no_credentials() -> Mock:
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(None, CredentialsSource.NONE)
    return provider


def _stream(
    credentials: Mock | None = None, task_manager: ITaskManager | None = None
) -> SpotUserDataStream:
    return SpotUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.SPOT_TESTNET),
        task_manager if task_manager is not None else Mock(),
        credentials if credentials is not None else _credentials(),
        FakeTradingAccountReader(),
        EquityCurveRecorder(),
    )


async def _run_with_sockets(
    stream: SpotUserDataStream,
    sockets: list[Socket],
    token: CancellationToken,
    *,
    create: Callable[..., Awaitable[Mock]] | None = None,
) -> list[float]:
    """Run the stream over `sockets` (the token is cancelled by the last one)
    and answer every delay it asked `asyncio.sleep` for."""
    delays: list[float] = []

    async def record_sleep(delay: float, *_args: object, **_kwargs: object) -> None:
        delays.append(delay)

    async def new_client(**_kwargs: object) -> Mock:
        return Mock(close_connection=AsyncMock())

    bsm = Mock()
    bsm.user_socket.side_effect = sockets
    stream._generation = 1
    with (
        patch("asyncio.sleep", new=record_sleep),
        patch(f"{_MODULE}.AsyncClient") as async_client,
        patch(f"{_MODULE}.BinanceSocketManager", return_value=bsm),
    ):
        async_client.create = create if create is not None else new_client
        await stream._run_stream(token, generation=1)
    assert bsm.user_socket.call_count == len(sockets), "every scripted socket opened"
    return delays


@pytest.mark.parametrize("failure", FAILURES, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize("at_enter", [True, False], ids=["on_entry", "on_recv"])
async def test_any_exception_from_the_socket_is_retried_not_fatal(
    failure: Exception, at_enter: bool
) -> None:
    """`test_a_value_error_from_the_socket_is_retried_with_backoff` of the task
    (EPIC-035B §5), over every failure mode the pinned library raises. Red
    before: only `OSError`/`ReadLoopClosed` were caught, the rest ended the task."""
    token = CancellationToken()
    sockets = [
        fail(failure, at_enter=at_enter),
        fail(failure, at_enter=at_enter),
        ends_the_stream(token),
    ]

    delays = await _run_with_sockets(_stream(), sockets, token)

    assert len(delays) == 2, "one backoff per failed attempt, none after the end"


async def test_the_delay_between_attempts_grows() -> None:
    token = CancellationToken()
    sockets = [fail(ValueError("x"), at_enter=True) for _ in range(5)]
    sockets.append(ends_the_stream(token))

    delays = await _run_with_sockets(_stream(), sockets, token)

    assert delays == sorted(delays)
    assert delays[-1] > delays[0] * 4, "exponential, not the old fixed 5 s"
    assert len(set(delays)) == len(delays), "growing, so never one fixed delay"


async def test_a_failure_while_creating_the_client_is_retried() -> None:
    """The client is created outside the loop today (`spot_user_data_stream.py:
    163`): an API error there (clock skew, a banned IP) ended the task."""
    token = CancellationToken()
    calls = 0

    async def flaky_create(**_kwargs: object) -> Mock:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise api_error()
        return Mock(close_connection=AsyncMock())

    delays = await _run_with_sockets(
        _stream(), [ends_the_stream(token)], token, create=flaky_create
    )

    assert calls == 3
    assert len(delays) == 2


async def test_a_cancelled_stream_does_not_reconnect() -> None:
    token = CancellationToken()
    token.cancel()

    delays = await _run_with_sockets(_stream(), [], token)

    assert delays == []


async def test_a_stream_that_ended_by_itself_can_be_started_again() -> None:
    """Red before: the task ended (no credentials) but `_task_handle` stayed
    set, so `start()` answered "already running" and returned False for ever."""
    manager = AsyncioTaskManager()
    stream = _stream(credentials=_no_credentials(), task_manager=manager)

    assert stream.start() is True
    await manager.handles[0].task

    assert stream.start() is True, "the dead task's handle was cleared"
    assert len(manager.handles) == 2


async def test_a_superseded_task_never_clears_a_newer_handle() -> None:
    """`stop()` then `start()` while the old coroutine is still tearing down:
    when the old one finally ends it must not null the new one's handle
    (`BUG-094`'s generation fence, applied to the handle)."""
    manager = AsyncioTaskManager()
    stream = _stream(task_manager=manager)
    gates = {1: asyncio.Event(), 3: asyncio.Event()}

    async def held_open(token: CancellationToken, generation: int) -> None:
        await gates[generation].wait()

    stream._run_stream = held_open  # type: ignore[method-assign]

    assert stream.start() is True  # generation 1
    assert stream.stop() is True  # generation 2: nothing runs under it
    assert stream.start() is True  # generation 3, the newer task
    older, newer = manager.handles

    gates[1].set()
    await older.task

    assert stream._task_handle is newer, "the old task left the newer handle alone"
    gates[3].set()
    await newer.task
    assert stream._task_handle is None, "the newer task cleared its own"


async def test_is_running_reports_what_is_true() -> None:
    manager = AsyncioTaskManager()
    stream = _stream(credentials=_no_credentials(), task_manager=manager)
    assert stream.is_running is False

    stream.start()
    assert stream.is_running is True

    await manager.handles[0].task
    assert stream.is_running is False


async def test_the_stream_publishes_connecting_connected_reconnecting_and_stopped() -> (
    None
):
    """The health sequence a venue's consumers see across a drop and a stop
    (EPIC-035B §5, `test_the_stream_publishes_connected_reconnecting_and_down`;
    'down' is the consumer's judgement of how long `RECONNECTING` lasted)."""
    bus = MemoryEventBus()
    seen: list[UserStreamState] = []
    bus.on(UserStreamHealthEvent, lambda e: seen.append(e.state))
    manager = AsyncioTaskManager()
    stream = SpotUserDataStream(
        venue_emitter(bus, TradingVenue.SPOT_TESTNET),
        manager,
        _credentials(),
        FakeTradingAccountReader(),
        EquityCurveRecorder(),
    )
    sockets = [fail(ValueError("dropped"), at_enter=False), Socket(on_recv=stream.stop)]
    bsm = Mock()
    bsm.user_socket.side_effect = sockets

    async def no_sleep(*_a: object, **_k: object) -> None:
        return None

    async def new_client(**_kwargs: object) -> Mock:
        return Mock(close_connection=AsyncMock())

    with (
        patch("asyncio.sleep", new=no_sleep),
        patch(f"{_MODULE}.AsyncClient") as async_client,
        patch(f"{_MODULE}.BinanceSocketManager", return_value=bsm),
    ):
        async_client.create = new_client
        assert stream.start() is True
        await manager.handles[0].task

    assert seen == [
        UserStreamState.CONNECTING,
        UserStreamState.CONNECTED,
        UserStreamState.RECONNECTING,
        UserStreamState.CONNECTED,
        UserStreamState.STOPPED,
    ]
