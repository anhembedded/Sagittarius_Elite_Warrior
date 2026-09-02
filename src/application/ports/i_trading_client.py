"""Application port for placing/canceling live orders and reading positions
on the trading venue (`EPIC-021E`).

@details Deliberately its own port, not an extension of `IExchangeClient`
(market data, `EPIC-021A`): Interface Segregation
(`architecture-rule.md` §1, ADR §2.1) — the two talk to two different
connections, one keyless, one signed. Folding order placement into
`IExchangeClient` would force every existing market-data implementer
(including ones in `tests/` and `scripts/`) to grow trading methods it
never uses, the exact shape `BUG-026` already named as a mistake. Grep all
three (`src/`, `scripts/`, `tests/`) for implementers before changing this
port's shape (`ONBOARDING.md` §8, bẫy 11).

Not implemented yet: this task is domain-and-port only, "không chạm mạng
một dòng nào" (`EPIC-021E` §1) — a concrete Binance-backed implementation
is `EPIC-021F`'s.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order


class ITradingClient(ABC):
    """Port for the one signed connection allowed to place, cancel, and
    read back live orders/positions on the trading venue."""

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        """@brief Sends `order` to the exchange.
        @return The same order as the exchange acknowledged it — at minimum
        with `status` advanced off `OrderStatus.NEW` if the exchange
        responded synchronously.
        """

    @abstractmethod
    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        """@brief Cancels one still-open order by its app-generated
        `client_order_id`.
        @return The order as the exchange reports it after the cancel
        request, with `status` reflecting whatever the exchange settled on
        (`OrderStatus.CANCELED`, or `OrderStatus.FILLED` if it filled before
        the cancel reached the exchange).
        """

    @abstractmethod
    def cancel_all_orders(self, symbol: str) -> list[Order]:
        """@brief Cancels every open order on `symbol`.
        @return The orders that were canceled. Empty if none were open.
        """

    @abstractmethod
    def get_open_orders(self, symbol: str) -> list[Order]:
        """@brief Lists every currently-open order on `symbol`."""

    @abstractmethod
    def get_positions(self, symbol: str) -> list[LivePosition]:
        """@brief Lists every open position on `symbol`.
        @return Empty if the account is flat on `symbol`. One-way mode
        (assumed throughout this epic) means at most one element.
        """
