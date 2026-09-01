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

    def create_futures_metadata_client(self) -> Client:
        """@brief A raw `python-binance` `Client`, always pointed at Futures
        Testnet, for reading `/fapi/v1/exchangeInfo` (`EPIC-021C`).
        @details Deliberately ignores `self._market_data_venue` — futures
        order metadata (`stepSize`/`tickSize`/`minNotional`) must always
        come from the same exchange an order will actually be sent to, which
        this epic never varies: `TradingVenue` has no `MAINNET` member (ADR
        §3), so `FUTURES_TESTNET` is the only futures venue that exists,
        independent of whatever the user's *chart data* venue is set to.
        No key attached, same reasoning as `create_market_data_client()`'s
        `MAINNET_PUBLIC` case — `exchangeInfo` is a public endpoint.
        Returns the raw SDK type rather than an `IExchangeClient`: this
        method is consumed only by other infrastructure code
        (`FuturesMetadataProvider`), never by `application/`, so there is no
        port to leak through (`architecture-rule.md` §3 concerns
        `application/ports/`, not infra-to-infra calls).
        """
        return Client(
            requests_params={"timeout": _DEFAULT_REQUEST_TIMEOUT_SECONDS},
            testnet=True,
        )
