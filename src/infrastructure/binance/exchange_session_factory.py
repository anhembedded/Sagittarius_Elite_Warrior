"""The one place in the app allowed to call `binance.client.Client(...)`
(`EPIC-021A`). Locked by `tests/unit/infrastructure/binance/
test_only_the_session_factory_constructs_binance_client.py`, which scans
`src/`+`scripts/` by AST for any other call site."""

from __future__ import annotations

from binance.client import Client
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_session_factory import (
    IExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_endpoints import (
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    PythonBinanceClient,
)

#: BUG-063 — python-binance's own default read timeout is 10s. A multi-day
#: 1-second-interval sync needs hundreds of sequential requests, so at that
#: default, an ordinary slow response (not an outage) was enough to fail the
#: whole sync. 30s is still bounded — a genuinely dead connection fails loud
#: well within human patience — but stops treating an occasional slow page as
#: fatal.
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0


class ExchangeSessionFactory(IExchangeSessionFactory):
    """@brief Builds `IExchangeClient` sessions for one configured
    `MarketDataVenue` (`EPIC-021A`).
    @details No key is attached for `MAINNET_PUBLIC` — kline/exchangeInfo
    reads are public endpoints, and a market-data-only client has no
    business holding credentials it never signs anything with (ADR §2.1).
    """

    def __init__(self, market_data_venue: MarketDataVenue) -> None:
        self._market_data_venue = market_data_venue

    def create_market_data_client(self) -> IExchangeClient:
        session = Client(
            requests_params={"timeout": _DEFAULT_REQUEST_TIMEOUT_SECONDS},
            testnet=resolve_testnet_flag(self._market_data_venue),
        )
        return PythonBinanceClient(
            client=session, market_data_venue=self._market_data_venue
        )
