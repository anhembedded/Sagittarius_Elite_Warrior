"""`market_data`'s own session factory (`EPIC-025` PR 1.3c-4).

Half of what `ExchangeSessionFactory` used to be. That class implemented two
contexts' ports from the legacy tree and had to import this module's
`PythonBinanceClient` to do it — one of the four boundary entries this split
retires. Here the wrapping is an intra-module call: the factory and the client
it wraps are the same module's adapters.

@par On constructing the SDK session here
`EPIC-021A` put every `binance.client.Client(...)` call in one file, and
`tests/unit/architecture/test_only_the_session_factory_constructs_binance_client.py`
holds that by exact equality. After the split there are two files, and its
allowed set names both: the rule was never "one file" for its own sake but
"only a session factory mints a session, so venue flags and credentials are
not scattered". This class is one of the two session factories, and it mints
the only kind of session `market_data` has — unsigned, public, no credential
anywhere near it (ADR §2.1).
"""

from __future__ import annotations

from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.client import (
    PythonBinanceClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_session_factory import (
    IExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    REQUEST_TIMEOUT_SECONDS,
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


class MarketDataSessionFactory(IExchangeSessionFactory):
    """Builds `IExchangeClient` sessions for one configured
    `MarketDataVenue` (`EPIC-021A`)."""

    def __init__(self, market_data_venue: MarketDataVenue) -> None:
        self._market_data_venue = market_data_venue

    def create_market_data_client(self) -> IExchangeClient:
        """No key is attached, for any venue: klines and `exchangeInfo` are
        public endpoints, and a market-data client has no business holding
        credentials it never signs anything with (ADR §2.1)."""
        session = Client(
            requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
            testnet=resolve_testnet_flag(self._market_data_venue),
        )
        return PythonBinanceClient(
            client=session, market_data_venue=self._market_data_venue
        )
