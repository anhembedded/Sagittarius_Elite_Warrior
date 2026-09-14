"""`EPIC-024A` — port covering the one thing `ExecuteOrderCommandHandler`,
`EnableTradingCommandHandler` and `EmergencyStopCommandHandler` actually
need from `ExchangeSessionFactory`: a signed session to hand to
`FuturesTradingClient`.

@details Before this port existed, all three handlers depended on the
*concrete* `ExchangeSessionFactory`/`FuturesTradingClient` classes directly
— an `architecture-rule.md` §3 violation confirmed at `PRO-003` §2.
`IExchangeSessionFactory` (`EPIC-021A`) could not simply grow a
`create_trading_client()` method to fix this: that port's own docstring
already rules it out — "this port must not name `binance.client.Client` in
its own signature" — and `create_trading_client()` on the concrete class
returns exactly that raw SDK type.

The fix here is Interface Segregation (same reasoning `i_trading_client.py`
already gives for being its own port, not folded into `IExchangeClient`),
plus a structural (`Protocol`) return type instead of the raw SDK class:
`ITradingSessionClient` names every `futures_*` call any consumer of
`create_trading_client()` actually makes — `FuturesTradingClient`
(`EPIC-021F`) and `FuturesAccountReader` (`EPIC-021D`) both resolve the
same client through `ExchangeSessionFactory`, so the Protocol has to cover
both, not just the port's own two application-layer callers.
`binance.client.Client` satisfies it structurally — it is never imported
here, so nothing in `application/` gains a dependency on `python-binance`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)


class ITradingSessionClient(Protocol):
    """@brief Structural port for the raw signed session
    `ExchangeSessionFactory.create_trading_client()` returns. Lists every
    `futures_*` call its two consumers (`FuturesTradingClient`,
    `FuturesAccountReader`) actually make — not a stand-in for the whole
    `python-binance` `Client` surface."""

    def futures_create_test_order(self, **params: Any) -> dict[str, Any]: ...

    def futures_create_order(self, **params: Any) -> dict[str, Any]: ...

    def futures_cancel_order(
        self,
        symbol: str,
        origClientOrderId: str,  # noqa: N803 - Binance's own REST param name, called by keyword
    ) -> dict[str, Any]: ...

    def futures_cancel_all_open_orders(self, symbol: str) -> dict[str, Any]: ...

    def futures_get_open_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_position_information(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_ping(self) -> dict[str, Any]: ...

    def futures_time(self) -> dict[str, Any]: ...

    def futures_account(self, **params: Any) -> dict[str, Any]: ...

    def futures_get_position_mode(self, **params: Any) -> dict[str, Any]: ...


class ITradingSessionFactory(ABC):
    """Port for the one place allowed to mint a signed trading session for
    `FuturesTradingClient` to drive."""

    @abstractmethod
    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        """@brief A signed session, authenticated with `credentials`, ready
        to place/cancel orders and read positions.
        @details Always Futures Testnet on every implementation this app
        ships (`TradingVenue` has no `MAINNET` member, ADR §3) — this port
        does not parameterize venue because there is never a second one to
        choose between.
        """
