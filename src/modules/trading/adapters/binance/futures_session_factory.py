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
    # than it sounds: this is the one call a fresh signing session makes
    # before its first real request, since `_futures_client()` turns off the
    # construction-time ping (`EPIC-028P`).
    local_at_measurement_ms = (local_before_ms + local_after_ms) // 2
    client.timestamp_offset = server_time_ms - local_at_measurement_ms


def _futures_client(credentials: ExchangeCredentials | None = None) -> Client:
    """`EPIC-028P` — a `python-binance` client for the Futures testnet,
    without the construction-time ping.

    @details `Client(...)` pings `GET /api/v3/ping` by default, which is the
    **Spot** API (`testnet.binance.vision` with `testnet=True`), whatever
    the client is then used for. Every Futures session therefore reached
    the Spot venue, and a Spot testnet outage failed Futures order, cancel
    and Emergency Stop calls before they sent anything. The dual-venue
    integration test (`test_two_venues_in_one_process_against_fake_server.
    py`) caught it. The Futures session has its own first round trip,
    `futures_time()` in `_sync_timestamp_offset`, so nothing is lost.
    """
    return Client(
        api_key=credentials.api_key if credentials else None,
        api_secret=credentials.api_secret if credentials else None,
        requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
        testnet=True,
        ping=False,
    )


class FuturesSessionFactory(ITradingSessionFactory):
    """Mints this module's Futures Testnet sessions, signed and unsigned.

    Always Futures Testnet, never parameterized by venue: `TradingVenue` has
    no `MAINNET` member (ADR §3), so there is never a second one to choose
    between — and futures order metadata (`stepSize`/`tickSize`/
    `minNotional`) must come from the same exchange an order will actually be
    sent to, independent of whatever the user's *chart data* venue is set to.
    """

    def create_futures_metadata_client(self) -> Client:
        """An unsigned Futures Testnet session for the public endpoints:
        `/fapi/v1/exchangeInfo` (`EPIC-021C`), and `ticker/bookTicker` and
        `premiumIndex` (`EPIC-028O`). No key: all three are public. Returns
        the raw SDK type because the only callers are this module's own
        `FuturesMetadataProvider`, `FuturesBookTickerReader` and
        `FuturesMarkPriceReader` — see the module docstring for why that is
        not a leak."""
        return _futures_client()

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
        client = _futures_client(credentials)
        _sync_timestamp_offset(client)
        return cast(ITradingSessionClient, client)
