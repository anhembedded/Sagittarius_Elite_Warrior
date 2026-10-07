"""The verified fake for `IMarketDataSources` (HLD §10.3, `BUG-172`).

**Who needs it.** A consumer of a venue's market data — a desk, a bot's chart, a
backtest — resolves `IMarketDataSources` and asks for its venue's ports, and the
port is a *foreign* one to every consumer, so `Mock(spec=IMarketDataSources)` is
not an option (`test_no_foreign_port_is_mocked.py`).

**Strict on purpose.** A venue nobody registered raises: a consumer that asks for
the wrong venue's ports fails its test instead of being handed a stand-in that
answers for everything, which is the very mix-up the port exists to prevent.
`serving` registers a venue; `FakeMarketDataSources.ports` builds the four ports
from the other verified fakes.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
    MarketDataPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    FakeRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


class FakeMarketDataSources(IMarketDataSources):
    """Each registered venue's ports; any other venue is an error."""

    def __init__(
        self,
        ports: Mapping[MarketDataVenue, MarketDataPorts] | None = None,
        default: MarketDataVenue = MarketDataVenue.MAINNET_PUBLIC,
    ) -> None:
        self._default = default
        self._ports: dict[MarketDataVenue, MarketDataPorts] = dict(ports or {})
        #: Every venue asked for, in order, so a test can see where a consumer went.
        self.asked: list[MarketDataVenue] = []

    @staticmethod
    def ports(
        venue: MarketDataVenue,
        *,
        sync: IMarketDataSync | None = None,
        history: IHistoricalKlines | None = None,
        stream: IMarketStream | None = None,
        repository: IMarketDataRepository | None = None,
    ) -> MarketDataPorts:
        """`venue`'s four ports, each a fresh verified fake unless given."""
        return MarketDataPorts(
            venue=venue,
            sync=sync or FakeMarketDataSync(),
            history=history or FakeHistoricalKlines(),
            stream=stream or FakeMarketStream(),
            coverage=FakeRangeCoverage(),
            repository=repository or FakeMarketDataRepository(),
        )

    def serving(self, ports: MarketDataPorts) -> FakeMarketDataSources:
        """Registers `ports` as its venue's."""
        self._ports[ports.venue] = ports
        return self

    @property
    def default_venue(self) -> MarketDataVenue:
        return self._default

    def ports_for(self, venue: MarketDataVenue) -> MarketDataPorts:
        self.asked.append(venue)
        try:
            return self._ports[venue]
        except KeyError:
            raise AssertionError(
                f"no market data was registered for {venue.value}: the consumer "
                "asked for a venue the test did not expect"
            ) from None
