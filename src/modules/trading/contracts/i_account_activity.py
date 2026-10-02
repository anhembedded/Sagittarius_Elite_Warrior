"""`EPIC-028J` — port: what a desk shows about its account besides
positions, read from the venue rather than only from events.

@details Bound to one venue, like every port in `VenueTradingPorts`: the
Spot desk's tabs read Spot orders and Spot fills. A desk opened after an
order was placed elsewhere (another desk, Binance's own UI) still lists it,
because these are reads of the account, not a record of what this app sent.

Positions and Spot holdings are not here: `IAccountSnapshot` already reads
them.

Plausible extensions, each one new method here plus its query:
- the Futures funding fee history (`GET /fapi/v1/income`);
- a Spot conversion or deposit history;
- a mainnet venue, which needs nothing here: another `VenueTradingPorts`.

Every method is a network read, so a caller runs it off the UI thread.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


class IAccountActivity(ABC):
    """One venue's account summary, open orders and histories."""

    @abstractmethod
    def summary(self) -> AccountSummary | None:
        """Read the account's spendable balance and value.
        @return `None` when the account could not be read; the venue's
        connection status names why."""

    @abstractmethod
    def open_orders(self) -> tuple[Order, ...]:
        """Every order open on the account, on every symbol, whoever placed
        it."""

    @abstractmethod
    def order_history(self, request: HistoryRequest) -> HistoryPage[OrderRecord]:
        """One page of the account's orders, newest first.
        @raise AccountHistoryUnavailableError The venue did not answer."""

    @abstractmethod
    def trade_history(self, request: HistoryRequest) -> HistoryPage[TradeRecord]:
        """One page of the account's fills, newest first.
        @raise AccountHistoryUnavailableError The venue did not answer."""
