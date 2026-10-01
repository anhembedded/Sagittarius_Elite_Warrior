"""`EPIC-028J` — `IAccountActivity`'s verified fake.

@details Answers what a test seeds: a summary, the open orders, and each
history's rows, which it cuts into `HISTORY_PAGE_SIZE` pages in the order
given (a test seeds them newest first, as the venue answers). Every history
request is recorded, so a test can show that paging keeps its `since`.
An unseeded summary is `None`, the port's own answer for an account that
could not be read; a seeded error is raised by both history reads.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


class FakeAccountActivity(IAccountActivity):
    """The account a test says the venue reports."""

    def __init__(self) -> None:
        self._summary: AccountSummary | None = None
        self._open_orders: tuple[Order, ...] = ()
        self._order_rows: tuple[OrderRecord, ...] = ()
        self._trade_rows: tuple[TradeRecord, ...] = ()
        self._scanned: tuple[str, ...] = ()
        self._notices: tuple[str, ...] = ()
        self._history_error: Exception | None = None
        #: Every `order_history` request, in order.
        self.order_requests: list[HistoryRequest] = []
        #: Every `trade_history` request, in order.
        self.trade_requests: list[HistoryRequest] = []
        self.open_order_reads = 0

    def holding_summary(self, summary: AccountSummary | None) -> None:
        self._summary = summary

    def holding_open_orders(self, orders: Iterable[Order]) -> None:
        self._open_orders = tuple(orders)

    def holding_history(
        self,
        orders: Iterable[OrderRecord] = (),
        trades: Iterable[TradeRecord] = (),
        *,
        scanned_symbols: tuple[str, ...] = (),
        notices: tuple[str, ...] = (),
    ) -> None:
        """Seeds both histories, newest first. `scanned_symbols` is what a
        page for every pair names; a one-symbol page names its symbol."""
        self._order_rows = tuple(orders)
        self._trade_rows = tuple(trades)
        self._scanned = scanned_symbols
        self._notices = notices

    def history_raises(self, error: Exception) -> None:
        self._history_error = error

    def summary(self) -> AccountSummary | None:
        return self._summary

    def open_orders(self) -> tuple[Order, ...]:
        self.open_order_reads += 1
        return self._open_orders

    def order_history(self, request: HistoryRequest) -> HistoryPage[OrderRecord]:
        self.order_requests.append(request)
        rows = [r for r in self._order_rows if _kept(r.order.symbol, request)]
        return self._page(rows, request)

    def trade_history(self, request: HistoryRequest) -> HistoryPage[TradeRecord]:
        self.trade_requests.append(request)
        rows = [r for r in self._trade_rows if _kept(r.symbol, request)]
        return self._page(rows, request)

    def _page[T](self, rows: list[T], request: HistoryRequest) -> HistoryPage[T]:
        if self._history_error is not None:
            raise self._history_error
        start = request.page * HISTORY_PAGE_SIZE
        return HistoryPage(
            rows=tuple(rows[start : start + HISTORY_PAGE_SIZE]),
            page=request.page,
            total_rows=len(rows),
            scanned_symbols=(
                (request.symbol,) if request.symbol is not None else self._scanned
            ),
            notices=self._notices,
        )


def _kept(symbol: str, request: HistoryRequest) -> bool:
    return request.symbol is None or symbol == request.symbol
