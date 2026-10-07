"""Port: *the market data of one venue* (`BUG-172`).

**The rule it states.** A screen that acts on a trading venue shows the market
of that venue — Spot Testnet charts `testnet.binance.vision`, Futures Testnet the
futures testnet, both mainnet venues the public mainnet — so the price a person
looks at is the price their order fills at. Before `BUG-172` one process-wide
setting decided it for every venue, and two of the four were always wrong.

**The shape.** `ports_for(venue)` returns the four ports bound to that venue's
market: what a sync fetches and stores, what a read returns, what a stream
opens and what a coverage check counts all belong to it and to no other. The
caller picks the venue once, where it is built, and then uses the ports it
already knew (`IMarketDataSync`, `IHistoricalKlines`, `IMarketStream`,
`IRangeCoverage`) unchanged; the same venue always answers with the same
objects, so a stream owner and its sync agree.

A screen with no venue (Data mode, a plain historical backtest) resolves the
four ports directly from the container: they are `ports_for(default venue)`,
where the default is the public mainnet (`DEFAULT_MARKET_DATA_VENUE`, not a
setting).

Seam now, variant later (`architecture-rule.md` §7.2.1): a venue is one more
`MarketDataVenue` member and one line in `TradingVenue.market_data_venue`; no
consumer changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


@dataclass(frozen=True, slots=True)
class MarketDataPorts:
    """One venue's market data, as the four ports a screen reads it through."""

    venue: MarketDataVenue
    sync: IMarketDataSync
    history: IHistoricalKlines
    stream: IMarketStream
    coverage: IRangeCoverage
    #: The venue's candle store itself, for a consumer that streams rows or counts
    #: them (`RunGridBacktestQuery`): the same store `history` reads.
    repository: IMarketDataRepository


class IMarketDataSources(ABC):
    """Hands out each venue's market-data ports."""

    @property
    @abstractmethod
    def default_venue(self) -> MarketDataVenue:
        """The venue of the screens that act on none (Data mode, a plain
        historical backtest): the public mainnet, not a setting."""

    @abstractmethod
    def ports_for(self, venue: MarketDataVenue) -> MarketDataPorts:
        """The ports bound to `venue`'s market; the same object on every call."""
