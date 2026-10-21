"""`BUG-263` - the kline stream cancelled while it creates its client leaves no open HTTP session.

@details The same hole as the user-data streams': the library's `AsyncClient.create` opens a session
and closes it only for an `Exception`, not for the `CancelledError` of a host stop. The real client
runs with only its ping held back.
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

import pytest
from binance import AsyncClient
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Sagittarius_Elite_Warrior.tests.aiohttp_sessions import record_sessions
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


async def test_cancelling_the_stream_during_its_clients_ping_closes_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = record_sessions(monkeypatch)
    entered = asyncio.Event()
    service = BinanceWebsocketService(Mock(), Mock())

    async def ping(_self: AsyncClient, *_a: object, **_k: object) -> None:
        entered.set()
        await asyncio.sleep(
            0.2
        )  # long enough to be cancelled in, short enough to finish after

    async def get_server_time(_self: AsyncClient) -> dict[str, int]:
        return {"serverTime": 0}

    with (
        patch.object(AsyncClient, "ping", ping),
        patch.object(AsyncClient, "get_server_time", get_server_time),
    ):
        task = asyncio.ensure_future(
            service._run_stream(
                MarketType.SPOT, [("BTCUSDT", "1m")], CancellationToken()
            )
        )
        await asyncio.wait_for(entered.wait(), timeout=3.0)
        task.cancel()
        await asyncio.wait({task}, timeout=5.0)

    assert sessions.opened, "the stream opened a client"
    assert sessions.unclosed() == []
