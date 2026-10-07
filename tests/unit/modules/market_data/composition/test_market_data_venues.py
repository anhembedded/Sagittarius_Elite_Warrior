"""`MarketDataVenues` (`BUG-172`) — the default venue is the container's own, every
other venue is built on first ask with a store, a stream and a client of its own."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition import (
    market_data_venues as module,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.market_data_venues import (
    MarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sqlalchemy import create_engine

_DEFAULT = MarketDataVenue.MAINNET_PUBLIC
_TESTNET = MarketDataVenue.SPOT_TESTNET


class _Container:
    """The one container this registry is composed from, with the three default
    bindings of the venue the app was configured for."""

    def __init__(self) -> None:
        self.container = StdLibContainer()
        self.repository = FakeMarketDataRepository()
        self.client, self.stream = (
            Mock(spec=IExchangeClient),
            Mock(spec=ILiveStreamService),
        )
        # A callable instance (every `Mock`) would be taken for a factory.
        self.container.singleton(IMarketDataRepository, lambda _c: self.repository)
        self.container.singleton(IExchangeClient, lambda _c: self.client)
        self.container.singleton(ILiveStreamService, lambda _c: self.stream)
        self.container.singleton(IEventBus, lambda _c: MemoryEventBus())
        self.container.singleton(ITaskManager, lambda _c: Mock())


@pytest.fixture
def world() -> _Container:
    return _Container()


@pytest.fixture
def venues(world: _Container, tmp_path: Path) -> Iterator[MarketDataVenues]:
    registry = MarketDataVenues(
        world.container, DatabaseConfig(db_dir=str(tmp_path)), _DEFAULT
    )
    yield registry
    registry.close()


def test_the_default_venue_is_the_containers_own_store_client_and_stream(
    venues: MarketDataVenues, world: _Container
) -> None:
    assert venues.default_venue is _DEFAULT
    assert venues.repository(_DEFAULT) is world.repository
    assert venues.exchange_client(_DEFAULT) is world.client
    assert venues.live_stream(_DEFAULT) is world.stream


def test_another_venue_has_a_store_and_a_stream_of_its_own(
    venues: MarketDataVenues, world: _Container
) -> None:
    assert venues.repository(_TESTNET) is not world.repository
    assert venues.live_stream(_TESTNET) is not world.stream
    assert venues.repository(_TESTNET) is venues.repository(_TESTNET)
    assert venues.live_stream(_TESTNET) is venues.live_stream(_TESTNET)


def test_two_other_venues_do_not_share_a_store(venues: MarketDataVenues) -> None:
    assert venues.repository(_TESTNET) is not venues.repository(
        MarketDataVenue.FUTURES_TESTNET
    )


def test_a_venues_store_is_a_directory_of_its_own(
    venues: MarketDataVenues, tmp_path: Path
) -> None:
    venues.repository(_TESTNET).save_klines(MarketType.SPOT, [candle("BTCUSDT", 0)])

    assert (tmp_path / _TESTNET.value / "spot_BTCUSDT.db").is_file()
    assert not (tmp_path / "spot_BTCUSDT.db").exists()


def test_a_venues_client_is_built_on_first_use_and_only_once(
    venues: MarketDataVenues,
) -> None:
    """Building one is a network call (`BUG-045`)."""
    with patch.object(module, "MarketDataSessionFactory") as factory:
        factory.return_value.create_market_data_client.return_value = Mock()

        venues.repository(_TESTNET)  # opening the store builds no client
        factory.assert_not_called()

        first = venues.exchange_client(_TESTNET)
        second = venues.exchange_client(_TESTNET)

    assert first is second
    factory.assert_called_once_with(_TESTNET)


def test_closing_stops_the_streams_and_closes_the_clients_it_built(
    venues: MarketDataVenues,
) -> None:
    with patch.object(module, "MarketDataSessionFactory") as factory:
        client = Mock()
        factory.return_value.create_market_data_client.return_value = client
        venues.exchange_client(_TESTNET)
        stream = venues.live_stream(_TESTNET)
        with patch.object(stream, "stop_all") as stop_all:
            venues.close()

    stop_all.assert_called_once_with()
    client.close.assert_called_once_with()


def test_closing_twice_and_closing_with_nothing_built_are_fine(
    venues: MarketDataVenues,
) -> None:
    venues.close()
    venues.close()


def test_closing_after_something_was_built_is_idempotent(
    venues: MarketDataVenues,
) -> None:
    venues.repository(_TESTNET)
    venues.close()
    venues.close()


def test_a_testnet_default_still_migrates_the_mainnets_legacy_shards(
    world: _Container, tmp_path: Path
) -> None:
    """The configured directory is the mainnet's whatever the default venue is:
    a shard written before `EPIC-027A` there is tagged Spot when the mainnet's
    store is first opened (ADR O3)."""
    legacy = tmp_path / "BTCUSDT.db"
    create_engine(f"sqlite:///{legacy}").dispose()
    legacy.touch()
    registry = MarketDataVenues(
        world.container, DatabaseConfig(db_dir=str(tmp_path)), _TESTNET
    )

    registry.repository(_DEFAULT)
    registry.close()

    assert (tmp_path / "spot_BTCUSDT.db").is_file()
    assert not legacy.exists()


def test_after_close_a_venue_is_an_error_not_a_store_nothing_would_close(
    venues: MarketDataVenues,
) -> None:
    """A worker still syncing at shutdown must fail loudly, not open a store the
    already-finished `close()` will never dispose."""
    venues.close()

    with pytest.raises(RuntimeError, match="after shutdown"):
        venues.repository(_TESTNET)


def test_one_step_failing_to_close_does_not_skip_the_rest(
    venues: MarketDataVenues,
) -> None:
    """Shutdown is best-effort: a stream that will not stop must not leave a store
    open, nor the next venue unclosed."""
    first = venues.live_stream(_TESTNET)
    second_repository = venues.repository(MarketDataVenue.FUTURES_TESTNET)
    with (
        patch.object(first, "stop_all", side_effect=OSError("socket")),
        patch.object(
            module.DatabaseManager, "dispose_all", autospec=True
        ) as dispose_all,
    ):
        venues.close()

    assert dispose_all.call_count == 2, "both stores were disposed"
    assert second_repository is not None


def test_a_client_asked_for_after_close_is_an_error_not_one_nothing_would_close(
    venues: MarketDataVenues,
) -> None:
    """A worker that fetched a venue's registry entry before `close()` and asks for
    its client after must not build a client the finished `close()` never closes."""
    held = venues._other(_TESTNET)
    venues.close()

    with pytest.raises(RuntimeError, match="after it was closed"):
        held.client()


def test_close_does_not_wait_for_a_client_that_is_still_being_built(
    venues: MarketDataVenues,
) -> None:
    """Building a client pings the network (`BUG-045`); a shutdown must not wait on
    it, and the client that finishes after `close()` is closed, not kept."""
    held = venues._other(_TESTNET)
    late_client = Mock()
    closed_while_building: list[bool] = []

    def building(_venue: MarketDataVenue) -> Mock:
        factory = Mock()

        def create() -> Mock:
            venues.close()  # returns at once: no lock is held across the ping
            closed_while_building.append(True)
            return late_client

        factory.create_market_data_client.side_effect = create
        return factory

    with (
        patch.object(module, "MarketDataSessionFactory", side_effect=building),
        pytest.raises(RuntimeError, match="after it was closed"),
    ):
        held.client()

    assert closed_while_building == [True]
    late_client.close.assert_called_once_with()
