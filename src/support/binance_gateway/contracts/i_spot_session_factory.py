"""`EPIC-027H`/`EPIC-027K` — port covering what `SpotAccountReader` and
`SpotTradingClient` need from a session factory: a signed session to read
Spot balances/prices through, and one to place/cancel Spot orders through.

@details `ITradingSessionFactory`'s own docstring rules out widening it for
this: "this port does not parameterize venue because there is never a
second one to choose between" — that assumption is no longer true now that
`TradingVenue.SPOT_TESTNET` exists, and `python-binance`'s Spot-side
methods (`ping`, `get_server_time`, `get_account`, `get_symbol_ticker`,
`create_order`, ...) are named differently from the `futures_*`-prefixed
ones that Protocol lists — so a Spot session needs its own, parallel, wide
port (mirroring `ITradingSessionFactory.create_trading_client()` ->
`ITradingSessionClient`, which already combines account-reading
(`futures_account`, `futures_position_information`) and order-placement
(`futures_create_order`, ...) in one protocol for Futures — the same shape
here, not a narrower split, since it is genuinely one signed session either
way).

`create_account_client()` and `create_trading_client()` are two minting
*methods* on one factory, not two ports: `SpotAccountReader` only calls the
first, `SpotTradingClient` only calls the second, but both return the same
`ISpotSessionClient` shape (the real signed session satisfies both
structurally) — same multi-method-one-factory shape this factory's own
`SpotSessionFactory` already has for `create_metadata_client()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)


class ISpotSessionClient(Protocol):
    """@brief Structural port for the raw signed session
    `create_account_client()`/`create_trading_client()` return. Lists only
    the calls `SpotAccountReader`, `SpotTradingClient` and
    `SpotHistoryReader` actually make — not a stand-in for the whole
    `python-binance` `Client` surface."""

    def ping(self) -> dict[str, Any]: ...

    def get_server_time(self) -> dict[str, Any]: ...

    def get_account(self, **params: Any) -> dict[str, Any]: ...

    def get_symbol_ticker(self, **params: Any) -> dict[str, Any]: ...

    def create_order(self, **params: Any) -> dict[str, Any]: ...

    def create_test_order(self, **params: Any) -> dict[str, Any]: ...

    def get_order(
        self,
        symbol: str,
        origClientOrderId: str,  # noqa: N803 - Binance's own REST param name, called by keyword
    ) -> dict[str, Any]: ...

    def cancel_order(self, **params: Any) -> dict[str, Any]: ...

    def get_open_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    def cancel_all_open_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    def get_all_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    def get_my_trades(self, **params: Any) -> list[dict[str, Any]]: ...


class ISpotSessionFactory(ABC):
    """Port for the one place allowed to mint a signed Spot session, for
    `SpotAccountReader` to read through or `SpotTradingClient` to trade
    through."""

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

    @abstractmethod
    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        """@brief A signed session, authenticated with `credentials`, ready
        to place/cancel orders and read open orders on Spot Testnet
        (`EPIC-027K`).
        @details Same real signed session shape as `create_account_client()`
        — kept as a separate minting method (not the same call reused)
        because the two are called from different modules for different
        reasons, mirroring `ITradingSessionFactory.create_trading_client()`'s
        own name and role on the Futures side.
        """
