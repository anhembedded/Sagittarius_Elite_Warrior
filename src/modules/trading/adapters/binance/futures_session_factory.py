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

from typing import cast

from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_sessions import (
    VenueSessions,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class FuturesSessionFactory(ITradingSessionFactory):
    """Mints one Futures venue's sessions, signed and unsigned, through
    `new_client`.

    A factory belongs to one venue, `FUTURES_TESTNET` or `FUTURES_MAINNET`, and
    every session it opens goes to that venue's exchange (`EPIC-034` D11), so
    futures order metadata (`stepSize`/`tickSize`/`minNotional`) comes from the
    same exchange an order will be sent to, whatever the user's *chart data*
    venue is set to.
    """

    def __init__(
        self,
        venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
        *,
        sessions: VenueSessions | None = None,
    ) -> None:
        if venue not in (TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET):
            raise ValueError(f"{venue.name} is not a Futures venue")
        self._venue = venue
        # `EPIC-035D` — one session per key, behind the venue's retry policy and
        # rate-limit gate, shared by every caller of this factory.
        self._sessions = sessions or VenueSessions(venue)
        if self._sessions.venue is not venue:
            raise ValueError(
                f"the sessions are for the venue {self._sessions.venue.name}, "
                f"not this factory's venue {venue.name}"
            )

    def create_futures_metadata_client(self) -> Client:
        """An unsigned Futures session for the public endpoints:
        `/fapi/v1/exchangeInfo` (`EPIC-021C`), and `ticker/bookTicker` and
        `premiumIndex` (`EPIC-028O`). No key: all three are public. Returns
        the raw SDK type because the only callers are this module's own
        `FuturesMetadataProvider`, `FuturesBookTickerReader` and
        `FuturesMarkPriceReader` — see the module docstring for why that is
        not a leak."""
        return cast(Client, self._sessions.public())

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
        return cast(ITradingSessionClient, self._sessions.signed(credentials))
