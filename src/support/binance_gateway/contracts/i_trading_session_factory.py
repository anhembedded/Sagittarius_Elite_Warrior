"""`EPIC-024A` — port covering the one thing `ExecuteOrderCommandHandler`,
`EnsureSessionReadyCommandHandler` and `EmergencyStopCommandHandler` actually
need from a session factory: a signed session to hand to
`FuturesTradingClient`.

@details Before this port existed, all three handlers depended on the
*concrete* session factory and `FuturesTradingClient` classes directly
— an `architecture-rule.md` §3 violation confirmed at `PRO-003` §2.
`IExchangeSessionFactory` (`EPIC-021A`) could not simply grow a
`create_trading_client()` method to fix this — and after `EPIC-025` PR 1.3c-4
it could not at all, since the two ports are now implemented by two different
modules' adapters. Even then: that port's own docstring
already rules it out — "this port must not name `binance.client.Client` in
its own signature" — and `create_trading_client()` on the concrete class
returns exactly that raw SDK type.

The fix here is Interface Segregation (same reasoning `i_trading_client.py`
already gives for being its own port, not folded into `IExchangeClient`),
plus a structural (`Protocol`) return type instead of the raw SDK class:
`ITradingSessionClient` names every `futures_*` call any consumer of
`create_trading_client()` actually makes — `FuturesTradingClient`
(`EPIC-021F`) and `FuturesAccountReader` (`EPIC-021D`) both resolve the
same client through this port, so the Protocol has to cover
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
    `create_trading_client()` returns. Lists every
    `futures_*` call its consumers (`FuturesTradingClient`,
    `FuturesAccountReader`, `FuturesHistoryReader`, `FuturesAccountControl`,
    `FuturesCommissionRateReader`) actually make — not a
    stand-in for the whole
    `python-binance` `Client` surface."""

    #: The exchange's clock less this machine's, in milliseconds, measured when
    #: the session was opened (`BUG-111`); a history read translates by it
    #: (`BUG-189`).
    timestamp_offset: int

    def futures_create_test_order(self, **params: Any) -> dict[str, Any]: ...

    def futures_create_order(self, **params: Any) -> dict[str, Any]: ...

    def futures_get_order(
        self,
        symbol: str,
        origClientOrderId: str,  # noqa: N803 - Binance's own REST param name, called by keyword
    ) -> dict[str, Any]: ...

    def futures_cancel_order(
        self,
        symbol: str,
        origClientOrderId: str,  # noqa: N803 - Binance's own REST param name, called by keyword
    ) -> dict[str, Any]: ...

    def futures_cancel_all_open_orders(self, symbol: str) -> dict[str, Any]: ...

    def futures_get_open_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    #: `EPIC-028R` — Binance's Algo Order API, where every USD-M conditional
    #: order lives (`futures_algo_order_mapper.py`).
    def futures_create_algo_order(self, **params: Any) -> dict[str, Any]: ...

    def futures_get_algo_order(self, **params: Any) -> dict[str, Any]: ...

    def futures_get_open_algo_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_get_all_algo_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_cancel_algo_order(self, **params: Any) -> dict[str, Any]: ...

    def futures_cancel_all_algo_open_orders(self, **params: Any) -> dict[str, Any]: ...

    def futures_position_information(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_ping(self) -> dict[str, Any]: ...

    def futures_time(self) -> dict[str, Any]: ...

    def futures_account(self, **params: Any) -> dict[str, Any]: ...

    def futures_get_position_mode(self, **params: Any) -> dict[str, Any]: ...

    def futures_get_all_orders(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_account_trades(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_change_leverage(self, **params: Any) -> dict[str, Any]: ...

    def futures_change_margin_type(self, **params: Any) -> dict[str, Any]: ...

    def futures_commission_rate(self, **params: Any) -> dict[str, Any]: ...

    def futures_income_history(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_symbol_config(self, **params: Any) -> list[dict[str, Any]]: ...

    def futures_get_multi_assets_mode(self) -> dict[str, Any]: ...

    def futures_leverage_bracket(
        self, **params: Any
    ) -> dict[str, Any] | list[dict[str, Any]]: ...


class ITradingSessionFactory(ABC):
    """Port for the one place allowed to mint a signed trading session for
    `FuturesTradingClient` to drive."""

    @abstractmethod
    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        """@brief A signed session, authenticated with `credentials`, ready
        to place/cancel orders and read positions.
        @details On the exchange of the venue the implementation was built
        for (`EPIC-034` D11): this port does not parameterize venue per call
        because one factory serves exactly one venue.
        """
