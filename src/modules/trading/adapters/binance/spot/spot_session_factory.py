"""`EPIC-027H`/`EPIC-027I`/`EPIC-027K` — mints a Spot venue's sessions, mirroring
`FuturesSessionFactory`, through `new_client` (`EPIC-034` D11: the one function
that constructs a `binance.client.Client`, with the venue's `testnet` flag), with
Spot's own unprefixed session-client methods (`ping`/`get_server_time`/
`get_account`/`get_exchange_info`/`create_order`) in place of Futures'
`futures_*` ones.

@details `create_metadata_client()` is on no port, same as
`FuturesSessionFactory.create_futures_metadata_client()`: its only caller is
this module's own `SpotMetadataProvider` (`EPIC-027I`), so the two talk
directly — a port exists to cross a boundary, and there is none here
(`architecture-rule.md` §2). `create_account_client()`/`create_trading_client()`
mint the same kind of signed session for two different callers
(`SpotAccountReader`/`SpotTradingClient`) — see `ISpotSessionFactory`'s own
docstring for why that is two methods, not one shared by both.
"""

from __future__ import annotations

from typing import cast

from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_client_builder import (
    new_client,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class SpotSessionFactory(ISpotSessionFactory):
    """Mints one Spot venue's sessions, signed and unsigned, through `new_client`.

    A factory belongs to one venue, `SPOT_TESTNET` or `SPOT_MAINNET`, and every
    session it opens goes to that venue's exchange (`EPIC-034` D11): the venue
    is the whole difference between the two, so `VenueAssembly` builds one per
    venue and no adapter chooses an endpoint itself.
    """

    def __init__(self, venue: TradingVenue = TradingVenue.SPOT_TESTNET) -> None:
        if venue not in (TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET):
            raise ValueError(f"{venue.name} is not a Spot venue")
        self._venue = venue

    def create_account_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        """A signed session, ready to read balances and prices
        (`EPIC-027H`).

        The `cast` only tells mypy what is already true: the object handed
        back satisfies `ISpotSessionClient` structurally, and `Client` is
        untyped third-party (see `pyproject.toml`'s mypy override), so
        returning it as-is would fail `no-any-return` against this method's
        own declared return type.
        """
        return cast(ISpotSessionClient, new_client(self._venue, credentials))

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        """A signed session, ready to place/cancel orders and read open
        orders (`EPIC-027K`). Same construction as `create_account_client()`
        — a real signed Spot session satisfies both structurally; kept as its
        own method because `SpotTradingClient` and `SpotAccountReader` call it
        for different reasons (see `ISpotSessionFactory`'s own docstring)."""
        return cast(ISpotSessionClient, new_client(self._venue, credentials))

    def create_metadata_client(self) -> Client:
        """An unsigned Spot session for the public endpoints:
        `GET /api/v3/exchangeInfo` (`EPIC-027I`) and
        `GET /api/v3/ticker/bookTicker` (`EPIC-028O`). No key: both are
        public. Returns the raw SDK type because the only callers are this
        module's own `SpotMetadataProvider` and `SpotBookTickerReader` — see
        the module docstring for why that is not a leak."""
        return new_client(self._venue)
