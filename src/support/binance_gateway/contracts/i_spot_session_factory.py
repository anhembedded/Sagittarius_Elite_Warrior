"""`EPIC-027H` — port covering the one thing `SpotAccountReader` needs from
a session factory: a signed session it can read Spot balances and prices
through.

@details `ITradingSessionFactory`'s own docstring rules out widening it for
this: "this port does not parameterize venue because there is never a
second one to choose between" — that assumption is no longer true now that
`TradingVenue.SPOT_TESTNET` exists, and `python-binance`'s Spot-side
methods (`ping`, `get_server_time`, `get_account`, `get_symbol_ticker`) are
named differently from the `futures_*`-prefixed ones that Protocol lists —
so a Spot session needs its own, parallel, narrow port (Interface
Segregation, the same reasoning `ITradingSessionFactory`'s own docstring
gives for being its own port rather than folded into `IExchangeClient`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)


class ISpotSessionClient(Protocol):
    """@brief Structural port for the raw signed session
    `create_account_client()` returns. Lists only the calls
    `SpotAccountReader` actually makes — not a stand-in for the whole
    `python-binance` `Client` surface."""

    def ping(self) -> dict[str, Any]: ...

    def get_server_time(self) -> dict[str, Any]: ...

    def get_account(self, **params: Any) -> dict[str, Any]: ...

    def get_symbol_ticker(self, **params: Any) -> dict[str, Any]: ...


class ISpotSessionFactory(ABC):
    """Port for the one place allowed to mint a signed Spot session for
    `SpotAccountReader` to read through."""

    @abstractmethod
    def create_account_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        """@brief A signed session, authenticated with `credentials`, ready
        to read balances and prices from Spot Testnet.
        @details Always Spot Testnet on every implementation this app ships
        (`TradingVenue` has no Spot mainnet member, ADR D8) — this port does
        not parameterize venue for the same reason `ITradingSessionFactory`
        does not.
        """
