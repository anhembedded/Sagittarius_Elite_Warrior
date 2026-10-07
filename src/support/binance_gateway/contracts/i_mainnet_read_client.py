"""`EPIC-034E` — the calls the read-only mainnet account makes, and no others.

@details A structural port (reason (c) of `architecture-rule.md` §2.1: the
implementer is third-party, python-binance's `Client`). It lists only reads:
there is no `create_order`, `create_test_order` or `cancel_order` here, so a
reader typed against it cannot call one. `ISpotSessionClient` is the trading
venues' and is never imported by the mainnet source
(`test_mainnet_has_no_order_path.py`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)


class IMainnetReadClient(Protocol):
    def ping(self) -> dict[str, Any]: ...

    def get_server_time(self) -> dict[str, Any]: ...

    def get_account(self) -> dict[str, Any]: ...

    def get_account_api_permissions(self) -> dict[str, Any]: ...

    def get_open_orders(self) -> list[dict[str, Any]]: ...

    def get_orderbook_ticker(self, *, symbol: str) -> dict[str, Any]: ...

    def get_exchange_info(self) -> dict[str, Any]: ...


class IMainnetReadSessionFactory(ABC):
    @abstractmethod
    def create_read_client(
        self, credentials: ExchangeCredentials
    ) -> IMainnetReadClient:
        """A signed mainnet session that can only read."""
