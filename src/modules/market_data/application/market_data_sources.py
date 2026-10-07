"""`IMarketDataSources`, assembled over the module's own services (`BUG-172`).

**What it adds.** Nothing a service did not already do: it builds, once per
venue, the sync and stream services bound to that venue and the reader and the
coverage check over that venue's store, and hands the four back as one
`MarketDataPorts`. The sync and the stream still dispatch the module's own
commands (`MarketDataSyncService`, `MarketStreamService`), so there is one
execution path per use case whatever the venue.

Built on first ask and kept: a stream owner and its sync must find the same
objects on every call, and a venue nobody opens costs nothing — no store is
created and no connection is opened until a screen asks for that venue.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_backtest_range_coverage import (
    RangeCoverageService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.market_stream_service import (
    MarketStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.market_data_sync_service import (
    MarketDataSyncService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
    MarketDataPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


class MarketDataSources(IMarketDataSources):
    """One `MarketDataPorts` per venue, built when first asked for."""

    def __init__(
        self, dispatcher: ICommandDispatcher, venues: IMarketDataVenues
    ) -> None:
        self._dispatcher = dispatcher
        self._venues = venues
        #: Screens on different worker threads may ask for the same venue at once.
        self._lock = threading.Lock()
        self._ports: dict[MarketDataVenue, MarketDataPorts] = {}

    @property
    def default_venue(self) -> MarketDataVenue:
        return self._venues.default_venue

    def ports_for(self, venue: MarketDataVenue) -> MarketDataPorts:
        with self._lock:
            ports = self._ports.get(venue)
            if ports is None:
                ports = self._build(venue)
                self._ports[venue] = ports
            return ports

    def _build(self, venue: MarketDataVenue) -> MarketDataPorts:
        repository = self._venues.repository(venue)
        return MarketDataPorts(
            venue=venue,
            sync=MarketDataSyncService(self._dispatcher, venue),
            history=StoredKlinesReader(repository),
            stream=MarketStreamService(self._dispatcher, venue),
            coverage=RangeCoverageService(repository),
            repository=repository,
        )
