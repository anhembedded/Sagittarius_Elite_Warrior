"""Port: *the infrastructure of each market-data venue* (`BUG-172`).

**Why this port exists.** Until `BUG-172` this context owned one exchange
client, one candle store and one live stream, all pointed at the single
process-wide `exchange.market_data_venue`. A desk on Spot Testnet therefore
charted mainnet prices while its orders filled on the testnet. A venue now has
its own three, and the use-case handlers (sync, stream) reach them through this
port by the venue their command names, so the handlers keep one execution path
through the dispatcher and know no concrete store, client or socket.

It is this context's own routing port: another context asks for ports with
`IMarketDataSources`, never for a store or a client.

**`default_venue`.** The setting for the screens that act on no venue (Data
mode, a plain historical backtest, the CLI). A command naming no venue means it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


class IMarketDataVenues(ABC):
    """The exchange client, candle store and live stream of one venue each."""

    @property
    @abstractmethod
    def default_venue(self) -> MarketDataVenue:
        """The venue of screens that act on none: `exchange.market_data_venue`."""

    @abstractmethod
    def exchange_client(self, venue: MarketDataVenue) -> IExchangeClient:
        """The venue's market-data client, built on first use (constructing one
        is a network call, `BUG-045`)."""

    @abstractmethod
    def repository(self, venue: MarketDataVenue) -> IMarketDataRepository:
        """The venue's candle store: kept apart from every other venue's, so a
        testnet candle is never served as a mainnet one."""

    @abstractmethod
    def live_stream(self, venue: MarketDataVenue) -> ILiveStreamService:
        """The venue's live kline stream; its ticks name the venue."""

    @abstractmethod
    def close(self) -> None:
        """Stops the streams, closes the clients and disposes the stores of the
        venues this port built itself. Idempotent."""
