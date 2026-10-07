"""The verified fake for `IMarketDataVenues` (HLD §10.3, `BUG-172`).

**Who needs it.** A test of the sync or the stream handler wants to say which
client, store and stream a venue has, and to see that the venue a command names
is the one used. It is the port's own routing and nothing else: every venue it
was not given answers with the one it was given for the default, which is what a
test of a single-venue behaviour wants, and `for_venue` replaces one venue's.
"""

from __future__ import annotations

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


class FakeMarketDataVenues(IMarketDataVenues):
    """Each venue's client, store and stream, as the test hands them in."""

    def __init__(
        self,
        client: IExchangeClient,
        repository: IMarketDataRepository,
        stream: ILiveStreamService,
        default: MarketDataVenue = MarketDataVenue.MAINNET_PUBLIC,
    ) -> None:
        self._default = default
        self._clients = {default: client}
        self._repositories = {default: repository}
        self._streams = {default: stream}
        self.closed = False

    def for_venue(
        self,
        venue: MarketDataVenue,
        client: IExchangeClient,
        repository: IMarketDataRepository,
        stream: ILiveStreamService,
    ) -> FakeMarketDataVenues:
        """Gives `venue` its own client, store and stream."""
        self._clients[venue] = client
        self._repositories[venue] = repository
        self._streams[venue] = stream
        return self

    @property
    def default_venue(self) -> MarketDataVenue:
        return self._default

    def exchange_client(self, venue: MarketDataVenue) -> IExchangeClient:
        return self._clients.get(venue, self._clients[self._default])

    def repository(self, venue: MarketDataVenue) -> IMarketDataRepository:
        return self._repositories.get(venue, self._repositories[self._default])

    def live_stream(self, venue: MarketDataVenue) -> ILiveStreamService:
        return self._streams.get(venue, self._streams[self._default])

    def close(self) -> None:
        self.closed = True
