"""A Spot venue the Grid executor can be run against, built from trading's ports.

`SimulatedBook` holds the account's open orders. `SimulatedSubmission` and
`SimulatedActivity` implement `IOrderSubmission` and `IAccountActivity` over it:
a LIMIT order rests until cancelled, a MARKET order is recorded and rests
nowhere, and every id is the one trading would generate for the request's tag.
A test scripts a refusal or a raise for the next submit or cancel. Fills are
not invented: a test feeds them to the executor, as the user data stream would.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

SYMBOL = "BTCUSDT"


class SimulatedBook:
    """The account's open orders, and what was asked of the venue."""

    def __init__(self) -> None:
        self.open: dict[str, Order] = {}
        self.requests: list[OrderRequest] = []
        self.cancels: list[str] = []
        #: Every order the venue accepted, market slices included, in order.
        self.submitted: list[str] = []
        self.threads: list[str] = []
        self.refuse_next: list[ExecuteOrderSafetyGate | None] = []
        self.raise_next: list[Exception] = []
        self.cancel_refusals: list[ExecuteOrderSafetyGate] = []
        #: Cancels that report done but leave the order open (a cancel the
        #: exchange has not applied yet).
        self.sticky: set[str] = set()
        #: Called at each cancel, before it applies: what a test observes
        #: about the world at that moment.
        self.cancel_probe: Callable[[], None] | None = None
        #: Orders that fill just before their cancel arrives: the cancel
        #: raises (Binance's -2011 "Unknown order sent.") and the order is gone.
        self.filled_before_cancel: set[str] = set()
        #: Cancels that raise with the order still open (the request was lost).
        self.cancel_raises: list[Exception] = []


class SimulatedSubmission(IOrderSubmission):
    def __init__(self, book: SimulatedBook) -> None:
        self._book = book

    def preview(self, request: OrderRequest) -> OrderPreview:
        raise AssertionError("the executor never previews")

    def submit(
        self, request: OrderRequest, *, live: bool = False
    ) -> ExecuteOrderResult:
        assert live, "a bot's orders are live"
        self._book.requests.append(request)
        self._book.threads.append(threading.current_thread().name)
        if self._book.raise_next:
            raise self._book.raise_next.pop(0)
        if self._book.refuse_next:
            gate = self._book.refuse_next.pop(0)
            if gate is not None:
                return ExecuteOrderResult(gate, None, (), None)
        order = Order(
            client_order_id=generate_client_order_id(request.client_order_tag),
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.reference_price
            if request.order_type is OrderType.LIMIT
            else None,
            time_in_force=request.time_in_force,
            quote_quantity=request.quote_quantity,
        )
        self._book.submitted.append(order.client_order_id)
        if request.order_type is OrderType.LIMIT:
            self._book.open[order.client_order_id] = order
        return ExecuteOrderResult(None, None, (), order)

    def validate(self, request: OrderRequest) -> Order:
        raise AssertionError("the executor never validates")

    def cancel(self, symbol: str, client_order_id: str) -> CancelOrderResult:
        self._book.cancels.append(client_order_id)
        if self._book.cancel_probe is not None:
            self._book.cancel_probe()
        if self._book.cancel_refusals:
            return CancelOrderResult(self._book.cancel_refusals.pop(0), None)
        if self._book.cancel_raises:
            raise self._book.cancel_raises.pop(0)
        if client_order_id in self._book.filled_before_cancel:
            self._book.open.pop(client_order_id, None)
            raise RuntimeError("APIError(code=-2011): Unknown order sent.")
        order = self._book.open.get(client_order_id)
        if client_order_id not in self._book.sticky:
            self._book.open.pop(client_order_id, None)
        return CancelOrderResult(None, order)


class SimulatedActivity(IAccountActivity):
    def __init__(self, book: SimulatedBook) -> None:
        self._book = book
        self.orders: list[OrderRecord] = []
        self.trades: list[TradeRecord] = []
        #: The venue does not answer history reads.
        self.history_unavailable = False
        #: How many times the open orders were read: a bot that parks or
        #: reconciles reads them, a bot at rest does not.
        self.open_order_reads = 0
        #: The venue's read of open orders raises this (the app is offline).
        self.open_orders_error: Exception | None = None

    def summary(self) -> AccountSummary | None:
        return None

    def open_orders(self) -> tuple[Order, ...]:
        self.open_order_reads += 1
        if self.open_orders_error is not None:
            raise self.open_orders_error
        return tuple(self._book.open.values())

    def order_history(self, request: HistoryRequest) -> HistoryPage[OrderRecord]:
        if self.history_unavailable:
            raise AccountHistoryUnavailableError("allOrders timed out")
        return HistoryPage(tuple(self.orders), 0, len(self.orders), (SYMBOL,))

    def trade_history(self, request: HistoryRequest) -> HistoryPage[TradeRecord]:
        return HistoryPage(tuple(self.trades), 0, len(self.trades), (SYMBOL,))
