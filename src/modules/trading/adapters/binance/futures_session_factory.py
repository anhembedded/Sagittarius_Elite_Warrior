"""`trading`'s own session factory (`EPIC-025` PR 1.3c-4).

The other half of `ExchangeSessionFactory`. Three of this module's adapters —
`FuturesAccountReader`, `FuturesMetadataProvider`, `FuturesUserDataStream` —
reached out of the module to that class in the legacy tree, which is three of
the four boundary entries this split retires. They reach this instead, and it
is theirs.

@par Two methods, one port
`create_trading_client()` is `ITradingSessionFactory`'s, the port
`support/binance_gateway` publishes because `trading`'s *application* layer
resolves it (`EPIC-024A`). `create_futures_metadata_client()` is on no port on
purpose: its only caller is `FuturesMetadataProvider`, this module's own
adapter, so the two talk directly — a port exists to cross a boundary, and
there is no boundary here (`architecture-rule.md` §2). Publishing one would
also mean naming the raw SDK `Client` in a contract, which
`IExchangeSessionFactory`'s docstring rules out.

@par On constructing the SDK session here
See `MarketDataSessionFactory`'s docstring for the same note: the
one-construction-site guard now names two files, one per context's session
factory, and the rule it enforces is unchanged — only a session factory mints
a session. This is the one that mints the **signed** one, which is why the
clock correction below lives here and not next to the public sessions.
"""

from __future__ import annotations

import time
from typing import cast

from binance.client import Client
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    REQUEST_TIMEOUT_SECONDS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)


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
    caller gets a freshly-constructed client per call anyway, so a
    correction applied only to caller-local state, or only once, would not
    help the ones built afterward. Set at the one place this module mints a
    signed session instead.
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


class FuturesSessionFactory(ITradingSessionFactory):
    """Mints this module's Futures Testnet sessions, signed and unsigned.

    Always Futures Testnet, never parameterized by venue: `TradingVenue` has
    no `MAINNET` member (ADR §3), so there is never a second one to choose
    between — and futures order metadata (`stepSize`/`tickSize`/
    `minNotional`) must come from the same exchange an order will actually be
    sent to, independent of whatever the user's *chart data* venue is set to.
    """

    def create_futures_metadata_client(self) -> Client:
        """An unsigned Futures Testnet session for `/fapi/v1/exchangeInfo`
        (`EPIC-021C`). No key: `exchangeInfo` is a public endpoint. Returns
        the raw SDK type because the only caller is this module's own
        `FuturesMetadataProvider` — see the module docstring for why that is
        not a leak."""
        return Client(
            requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
            testnet=True,
        )

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        """A signed session, ready to place and cancel orders and read
        positions (`EPIC-021D`) — the one client instance in this app allowed
        to sign a request (ADR §2.1).

        The `cast` only tells mypy what is already true: the object handed
        back satisfies `ITradingSessionClient` structurally, and `Client` is
        untyped third-party (see `pyproject.toml`'s mypy override), so
        returning it as-is would fail `no-any-return` against this method's
        own declared return type.
        """
        client = Client(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
            testnet=True,
        )
        _sync_timestamp_offset(client)
        return cast(ITradingSessionClient, client)
