"""`IMarketDataVenues`, assembled from the container (`BUG-172`).

**One venue is the container's own.** The default venue (`exchange.market_data_venue`)
keeps the bindings every consumer already resolves — `IMarketDataRepository`,
`IExchangeClient`, `ILiveStreamService` — so the CLI, the bulk sync, Data mode and
the shutdown order all stay as they were. Every other venue gets its own store,
client and stream, built here the first time something asks for it: no database
directory is created and no socket is opened for a venue nobody uses, and the
exchange client (whose constructor pings the network, `BUG-045`) is built only
when a sync or a symbol read reaches it.

A separate file from `adapter_bindings.py`: the bindings say *which class answers
a port*; this is a registry with a lifecycle (`close()`), which changes for
another reason.
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.market_data_session_factory import (
    MarketDataSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_directory import (
    venue_directory,
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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager

logger = logging.getLogger("App.MarketDataVenues")


class _VenueInfrastructure:
    """The store, the client and the stream of one venue that is not the default."""

    def __init__(
        self, venue: MarketDataVenue, base: DatabaseConfig, container: IContainer
    ) -> None:
        self.manager = DatabaseManager(
            DatabaseConfig(db_dir=venue_directory(base.db_dir, venue))
        )
        # Shards from before `EPIC-027A` are Spot (ADR O3); `label_legacy_store`
        # put them in the venue's store before anything reads them.
        self.manager.migrate_legacy_shards()
        self.repository = SQLAlchemyMarketDataRepository(self.manager)
        self.stream = BinanceWebsocketService(
            container.resolve(IEventBus), container.resolve(ITaskManager), venue
        )
        self._venue = venue
        self._client: IExchangeClient | None = None
        #: Two screens syncing the same venue on two workers must share one client,
        #: so one builds at a time; `_state_lock` guards only the fields, briefly.
        self._build_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._closed = False

    def client(self) -> IExchangeClient:
        with self._build_lock:
            with self._state_lock:
                self._refuse_if_closed()
                if self._client is not None:
                    return self._client
            # The network ping happens here, outside `_state_lock`: `close()` must
            # never wait on it.
            built = MarketDataSessionFactory(self._venue).create_market_data_client()
            with self._state_lock:
                if not self._closed:
                    self._client = built
                    return built
            built.close()
            self._refuse_if_closed()
            raise AssertionError("unreachable: the venue is closed")

    def _refuse_if_closed(self) -> None:
        if self._closed:
            raise RuntimeError(
                f"market data venue {self._venue.value}'s client was asked for "
                "after it was closed"
            )

    def close(self) -> None:
        """Every step runs even when an earlier one raises: shutdown is
        best-effort, and one venue's failure must not leave another's store open."""
        with self._state_lock:
            self._closed = True
            client = self._client
        for step, release in (
            ("stream", self.stream.stop_all),
            ("client", client.close if client is not None else _nothing),
            ("store", self.manager.dispose_all),
        ):
            try:
                release()
            except Exception as exc:  # noqa: BLE001 - shutdown must not raise; logged
                logger.warning(
                    "Market data venue %s: closing its %s failed: %s",
                    self._venue.value,
                    step,
                    exc,
                )


def _nothing() -> None:
    return None


class MarketDataVenues(IMarketDataVenues):
    """The default venue from the container; the others built on first ask."""

    def __init__(
        self, container: IContainer, base: DatabaseConfig, default: MarketDataVenue
    ) -> None:
        self._container = container
        self._base = base
        self._default = default
        self._lock = threading.Lock()
        self._others: dict[MarketDataVenue, _VenueInfrastructure] = {}
        self._closed = False

    @property
    def default_venue(self) -> MarketDataVenue:
        return self._default

    def exchange_client(self, venue: MarketDataVenue) -> IExchangeClient:
        if venue is self._default:
            return self._container.resolve(IExchangeClient)
        return self._other(venue).client()

    def repository(self, venue: MarketDataVenue) -> IMarketDataRepository:
        if venue is self._default:
            return self._container.resolve(IMarketDataRepository)
        return self._other(venue).repository

    def live_stream(self, venue: MarketDataVenue) -> ILiveStreamService:
        if venue is self._default:
            return self._container.resolve(ILiveStreamService)
        return self._other(venue).stream

    def close(self) -> None:
        """Stops every other venue's stream, closes its client and its store.
        The default venue's are the container's and are closed with it.

        Terminal: a venue asked for afterwards is an error, not a store nothing
        would ever close (a worker still syncing at shutdown fails loudly)."""
        with self._lock:
            self._closed = True
            built, self._others = list(self._others.values()), {}
        for infrastructure in built:
            infrastructure.close()

    def _other(self, venue: MarketDataVenue) -> _VenueInfrastructure:
        with self._lock:
            if self._closed:
                raise RuntimeError(
                    f"market data venue {venue.value} was asked for after shutdown"
                )
            infrastructure = self._others.get(venue)
            if infrastructure is None:
                infrastructure = _VenueInfrastructure(
                    venue, self._base, self._container
                )
                self._others[venue] = infrastructure
                logger.info("Market data venue %s opened.", venue.value)
            return infrastructure
