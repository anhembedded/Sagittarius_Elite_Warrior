"""`EPIC-035B` — the Futures user-data stream shares the Spot stream's defect
(`futures_user_data_stream.py:261`: `except (OSError, ReadLoopClosed)`, and a
`_task_handle` cleared only by `stop()`), so it gets the same fix by the same
mechanism (`UserStreamSupervisor`) and the same tests. See
`spot/test_spot_user_data_stream_resilience.py` for the reasoning."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
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
    "futures_user_data_stream"
)


def _provider(with_keys: bool) -> Mock:
    provider = Mock()
    credentials = ExchangeCredentials(api_key="key", api_secret="secret")
    provider.resolve.return_value = ResolvedCredentials(
        credentials if with_keys else None,
        CredentialsSource.FILE if with_keys else CredentialsSource.NONE,
    )
    return provider


def _stream(
    with_keys: bool = True, task_manager: ITaskManager | None = None
) -> FuturesUserDataStream:
    return FuturesUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.FUTURES_TESTNET),
        task_manager if task_manager is not None else Mock(),
        _provider(with_keys),
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )


async def _run_with_sockets(
    stream: FuturesUserDataStream,
    sockets: list[Socket],
    token: CancellationToken,
    *,
    create: Callable[..., Awaitable[Mock]] | None = None,
) -> list[float]:
    delays: list[float] = []

    async def record_sleep(delay: float, *_a: object, **_k: object) -> None:
        delays.append(delay)

    async def new_client(**_kwargs: object) -> Mock:
        return Mock(close_connection=AsyncMock())

    bsm = Mock()
    bsm.futures_user_socket.side_effect = sockets
    stream._generation = 1
    with (
        patch("asyncio.sleep", new=record_sleep),
        patch(f"{_MODULE}.AsyncClient") as async_client,
        patch(f"{_MODULE}.BinanceSocketManager", return_value=bsm),
    ):
        async_client.create = create if create is not None else new_client
        await stream._run_stream(token, generation=1)
    assert bsm.futures_user_socket.call_count == len(sockets)
    return delays


@pytest.mark.parametrize("failure", FAILURES, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize("at_enter", [True, False], ids=["on_entry", "on_recv"])
async def test_any_exception_from_the_socket_is_retried_not_fatal(
    failure: Exception, at_enter: bool
) -> None:
    token = CancellationToken()
    sockets = [
        fail(failure, at_enter=at_enter),
        fail(failure, at_enter=at_enter),
        ends_the_stream(token),
    ]

    delays = await _run_with_sockets(_stream(), sockets, token)

    assert len(delays) == 2


async def test_the_delay_between_attempts_grows() -> None:
    token = CancellationToken()
    sockets = [fail(ValueError("x"), at_enter=True) for _ in range(5)]
    sockets.append(ends_the_stream(token))

    delays = await _run_with_sockets(_stream(), sockets, token)

    assert delays == sorted(delays)
    assert delays[-1] > delays[0] * 4


async def test_a_failure_while_creating_the_client_is_retried() -> None:
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


async def test_a_stream_that_ended_by_itself_can_be_started_again() -> None:
    manager = AsyncioTaskManager()
    stream = _stream(with_keys=False, task_manager=manager)

    assert stream.start() is True
    await manager.handles[0].task

    assert stream.start() is True
    assert len(manager.handles) == 2


async def test_a_superseded_task_never_clears_a_newer_handle() -> None:
    manager = AsyncioTaskManager()
    stream = _stream(task_manager=manager)
    gates = {1: asyncio.Event(), 3: asyncio.Event()}

    async def held_open(token: CancellationToken, generation: int) -> None:
        await gates[generation].wait()

    stream._run_stream = held_open  # type: ignore[method-assign]

    assert stream.start() is True
    assert stream.stop() is True
    assert stream.start() is True
    older, newer = manager.handles

    gates[1].set()
    await older.task

    assert stream._task_handle is newer
    gates[3].set()
    await newer.task
    assert stream._task_handle is None


async def test_is_running_reports_what_is_true() -> None:
    manager = AsyncioTaskManager()
    stream = _stream(with_keys=False, task_manager=manager)
    assert stream.is_running is False

    stream.start()
    assert stream.is_running is True

    await manager.handles[0].task
    assert stream.is_running is False


async def test_the_stream_publishes_connecting_connected_reconnecting_and_stopped() -> (
    None
):
    bus = MemoryEventBus()
    seen: list[UserStreamState] = []
    bus.on(UserStreamHealthEvent, lambda e: seen.append(e.state))
    manager = AsyncioTaskManager()
    stream = FuturesUserDataStream(
        venue_emitter(bus, TradingVenue.FUTURES_TESTNET),
        manager,
        _provider(True),
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )
    bsm = Mock()
    bsm.futures_user_socket.side_effect = [
        fail(ValueError("dropped"), at_enter=False),
        Socket(on_recv=stream.stop),
    ]

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
