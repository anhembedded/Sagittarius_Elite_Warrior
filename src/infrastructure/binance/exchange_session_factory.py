"""The one place in the app allowed to call `binance.client.Client(...)`
(`EPIC-021A`). Locked by `tests/unit/infrastructure/binance/
test_only_the_session_factory_constructs_binance_client.py`, which scans
`src/`+`scripts/` by AST for any other call site."""

from __future__ import annotations

import time
from typing import cast

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
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

#: BUG-063 — python-binance's own default read timeout is 10s. A multi-day
#: 1-second-interval sync needs hundreds of sequential requests, so at that
#: default, an ordinary slow response (not an outage) was enough to fail the
#: whole sync. 30s is still bounded — a genuinely dead connection fails loud
#: well within human patience — but stops treating an occasional slow page as
#: fatal.
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0


def _sync_timestamp_offset(client: Client) -> None:
    """`BUG-111` — `python-binance` signs every request with
    `int(time.time() * 1000 + self.timestamp_offset)`
    (`base_client.py::_generate_signature`), and `timestamp_offset` defaults
    to `0`: an unsynced local clock is used verbatim. Binance's futures API
    rejects any signed request whose timestamp reads more than 1000ms ahead
    of the exchange's own clock (`-1021`) — a fixed threshold `recvWindow`
    does not widen (that parameter only extends how far *behind* is
    tolerated) — so a machine whose clock merely runs fast, even by a
    second, makes every signed call fail this way permanently, not
    intermittently. `FuturesAccountReader.check_connection()` already
    measures this exact skew via `futures_time()` for its own diagnostic
    display, but never applied it to a session's actual signing — and every
    caller here (`FuturesTradingClient`, `FuturesAccountReader`) gets a
    freshly-constructed client per call anyway, so a correction applied
    only to caller-local state, or only once, would not help the ones built
    afterward. Set at the one place every signed session is minted instead.
    """
    local_before_ms = int(time.time() * 1000)
    server_time_ms = int(client.futures_time()["serverTime"])
    local_after_ms = int(time.time() * 1000)
    # Midpoint of the round trip is the best available estimate of "local
    # time at the moment the server actually read its own clock" — cheaper
    # than it sounds: this is one extra HTTP call per already-freshly-built
    # signing session, the same cost `Client(...)`'s own construction-time
    # ping already pays (`BUG-045`).
    local_at_measurement_ms = (local_before_ms + local_after_ms) // 2
    client.timestamp_offset = server_time_ms - local_at_measurement_ms


class ExchangeSessionFactory(IExchangeSessionFactory, ITradingSessionFactory):
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

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        """@brief A raw `python-binance` `Client`, always Futures Testnet,
        signing with `credentials` (`EPIC-021D`).
        @details The one client instance in the app allowed to sign a
        request (ADR §2.1). Always `testnet=True`: `TradingVenue` has no
        `MAINNET` member (ADR §3), so this is never ambiguous. Declared as
        returning `ITradingSessionClient` (`EPIC-024A`) rather than the raw
        `Client` — the object handed back is still the same `Client`
        instance, which satisfies that structural port without this class
        needing to name it; the `cast` below only tells mypy so (`Client`
        is untyped third-party — see `pyproject.toml`'s mypy override —
        so returning it as-is would fail `no-any-return` against this
        method's own, non-`Any`, declared return type).

        `BUG-111` — every returned session has its `timestamp_offset`
        synced against the exchange's own clock before use (see
        `_sync_timestamp_offset()`'s docstring): without it, a signed
        request from a machine whose local clock runs even slightly fast
        fails every single time with Binance's `-1021` ("Timestamp for
        this request was ahead of the server's time"), since that
        threshold is fixed and not widened by `recvWindow`.
        """
        client = Client(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            requests_params={"timeout": _DEFAULT_REQUEST_TIMEOUT_SECONDS},
            testnet=True,
        )
        _sync_timestamp_offset(client)
        return cast(ITradingSessionClient, client)
