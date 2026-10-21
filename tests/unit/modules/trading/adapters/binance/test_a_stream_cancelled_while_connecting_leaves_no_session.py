"""`BUG-263` - a user-data stream cancelled while it creates its client leaves no open HTTP session.

@details The host's Stop opens the order session to cancel a bot's orders, which starts the user
stream, and the host stops a moment later: the stream task is cancelled inside `AsyncClient.create`
(its ping), and the library does not close the session it opened for `CancelledError`. The real
`AsyncClient` runs here with only its ping held back, so a stream that creates its client with
`AsyncClient.create` directly fails these tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import Mock, patch

import pytest
from binance import AsyncClient
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.managed_user_data_stream import (
    ManagedUserDataStream,
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
from Sagittarius_Elite_Warrior.tests.aiohttp_sessions import Sessions, record_sessions
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.asyncio_task_manager import (
    AsyncioTaskManager,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.emitter_builder import (
    venue_emitter,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _credentials() -> Mock:
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"), CredentialsSource.FILE
    )
    return provider


def _spot(tasks: AsyncioTaskManager) -> ManagedUserDataStream:
    return SpotUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.SPOT_TESTNET),
        tasks,
        _credentials(),
        FakeTradingAccountReader(),
        EquityCurveRecorder(),
    )


def _futures(tasks: AsyncioTaskManager) -> ManagedUserDataStream:
    return FuturesUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.FUTURES_TESTNET),
        tasks,
        _credentials(),
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )


def _ping_held_back(entered: asyncio.Event) -> Callable[..., Awaitable[None]]:
    async def hang(_self: AsyncClient, *_a: object, **_k: object) -> None:
        entered.set()
        await asyncio.sleep(
            0.2
        )  # long enough to be cancelled in, short enough to finish after

    return hang


@pytest.mark.parametrize("make", [_spot, _futures], ids=["spot", "futures"])
async def test_cancelling_the_stream_during_its_clients_ping_closes_the_session(
    monkeypatch: pytest.MonkeyPatch, make: Callable[[AsyncioTaskManager], object]
) -> None:
    sessions: Sessions = record_sessions(monkeypatch)
    entered = asyncio.Event()
    tasks = AsyncioTaskManager()
    stream = make(tasks)
    assert isinstance(stream, ManagedUserDataStream)

    async def get_server_time(_self: AsyncClient) -> dict[str, int]:
        return {"serverTime": 0}

    with (
        patch.object(AsyncClient, "ping", _ping_held_back(entered)),
        patch.object(AsyncClient, "get_server_time", get_server_time),
    ):
        assert stream.start()
        await asyncio.wait_for(entered.wait(), timeout=3.0)
        task = tasks.handles[0].task
        task.cancel()
        await asyncio.wait({task}, timeout=5.0)

    assert sessions.opened, "the stream opened a client"
    assert sessions.unclosed() == []
