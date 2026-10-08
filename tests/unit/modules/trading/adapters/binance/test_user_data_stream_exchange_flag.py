"""`EPIC-034` D11 — a venue's user data stream connects to that venue's exchange.

The stream's `AsyncClient.create(testnet=...)` is the one place a user data stream
decides which exchange it listens to: a mainnet venue's key sent to the testnet
stream (or the reverse) would be wrong silently, with every other test green. The
client is scripted and records how it was created; nothing is opened.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
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
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.emitter_builder import (
    venue_emitter,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_ADAPTERS = "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance."
_FUTURES = [TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET]
_SPOT = [TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET]


def _credentials() -> Mock:
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials("key", "secret"), CredentialsSource.ENV
    )
    return provider


class _CancelledOnceConnected:
    """A token that lets the stream start and is cancelled by the time it has
    created its client: the first question (`EPIC-035B`'s supervisor asks
    before it connects) is answered "no", every later one "yes"."""

    def __init__(self) -> None:
        self._asked = 0

    def is_cancelled(self) -> bool:
        self._asked += 1
        return self._asked > 1


async def _created_with(stream: Any, module: str) -> list[dict[str, object]]:
    """The keyword arguments `AsyncClient.create` got when `stream` connected."""
    created: list[dict[str, object]] = []

    async def create(**kwargs: object) -> Mock:
        created.append(kwargs)
        return Mock(close_connection=AsyncMock())

    with (
        patch(f"{_ADAPTERS}{module}.AsyncClient") as client,
        patch(f"{_ADAPTERS}{module}.BinanceSocketManager"),
    ):
        client.create = create
        stream._generation = 1
        await stream._run_stream(_CancelledOnceConnected(), generation=1)
    return created


@pytest.mark.parametrize("venue", _FUTURES)
async def test_a_futures_stream_connects_to_its_own_venues_exchange(
    venue: TradingVenue,
) -> None:
    stream = FuturesUserDataStream(
        venue_emitter(MemoryEventBus(), venue),
        Mock(),
        _credentials(),
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )

    (created,) = await _created_with(stream, "futures_user_data_stream")

    assert created["testnet"] is venue.is_testnet


@pytest.mark.parametrize("venue", _SPOT)
async def test_a_spot_stream_connects_to_its_own_venues_exchange(
    venue: TradingVenue,
) -> None:
    stream = SpotUserDataStream(
        venue_emitter(MemoryEventBus(), venue),
        Mock(),
        _credentials(),
        FakeTradingAccountReader(),
        EquityCurveRecorder(),
    )

    (created,) = await _created_with(stream, "spot.spot_user_data_stream")

    assert created["testnet"] is venue.is_testnet
