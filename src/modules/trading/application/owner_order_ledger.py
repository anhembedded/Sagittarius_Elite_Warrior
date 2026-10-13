"""`EPIC-029` ADR D6 — what one owner's orders commit, and when it sent them.

@details The part of an owner book the two kinds of book share (`EPIC-039D`):
the open orders by client order id with what each still commits, the fills
and ends the venue reported before `record_sent` ran (a market order can
fill while `place_order` is still returning), and the send times inside the
budget's window. What a fill does to the owner's holding (an inventory, a
signed position) is the book's own. Not thread-safe on its own: the books are
called under `TradingSessionState`'s lock.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)

_ZERO = Decimal(0)


@dataclass
class _OpenOrder:
    side: OrderSide
    #: The base the order was sent for. A quote-sized market buy carries
    #: the preview's estimate of the base it buys (`PreviewOrderQueryHandler`),
    #: which the fills can exceed.
    quantity: Decimal
    #: What it commits when nothing has filled: the BUY's notional.
    notional: Decimal
    #: A reduce-only order never adds to a position (Futures).
    reduce_only: bool
    filled: Decimal = _ZERO

    @property
    def remaining(self) -> Decimal:
        """Never below zero: a quote-sized buy can fill more base than its
        estimate before its last fill ends it (the `EPIC-029A` review)."""
        return max(self.quantity - self.filled, _ZERO)

    @property
    def committed_quote(self) -> Decimal:
        """A BUY's quote still at stake, in proportion to its base still
        unfilled. An order with no base to scale by commits its whole quote."""
        if self.side is not OrderSide.BUY:
            return _ZERO
        if self.quantity <= 0:
            return self.notional
        return self.notional * self.remaining / self.quantity


class OwnerOrderLedger:
    """One owner's open orders and recent sends."""

    def __init__(self, window: timedelta) -> None:
        self._window = window
        self._open: dict[str, _OpenOrder] = {}
        #: Fills and ends the venue reported before `record_sent` ran: the base
        #: filled so far, and whether the order is already over.
        self._early: dict[str, tuple[Decimal, bool]] = {}
        self._sends: deque[datetime] = deque()

    @property
    def open_order_count(self) -> int:
        return len(self._open)

    def open_buy_quote(self) -> Decimal:
        """The quote the open BUY orders still commit."""
        return sum((order.committed_quote for order in self._open.values()), _ZERO)

    def open_sell_quantity(self) -> Decimal:
        """The base the open SELL orders still commit."""
        return self.open_quantity(OrderSide.SELL)

    def open_quantity(self, side: OrderSide) -> Decimal:
        """The base the open orders of `side` could still trade."""
        return sum((o.remaining for o in self._open.values() if o.side is side), _ZERO)

    def open_adding_quantity(self, side: OrderSide) -> Decimal:
        """The base the open orders of `side` could still add to a position:
        reduce-only orders are left out."""
        return sum(
            (
                o.remaining
                for o in self._open.values()
                if o.side is side and not o.reduce_only
            ),
            _ZERO,
        )

    def time_since_last_send(self, now: datetime) -> timedelta | None:
        """@return `None` when the owner has sent nothing this session."""
        return now - self._sends[-1] if self._sends else None

    def orders_in_window(self, now: datetime) -> int:
        horizon = now - self._window
        return sum(1 for sent in self._sends if sent > horizon)

    def record_sent(self, order: Order, notional: Decimal, when: datetime) -> None:
        """@brief `order` reached the venue at `when`; `notional` is the
        quote it commits (the preview's estimate). A fill or an end the
        venue already reported for it is taken into account."""
        self._sends.append(when)
        horizon = when - self._window
        while self._sends and self._sends[0] <= horizon:
            self._sends.popleft()
        self._open_unless_over(order, notional)

    def adopt_open(self, order: Order, notional: Decimal) -> None:
        """@brief `order` was already resting on the venue when the budget
        was registered (a restart, a reconciliation): it commits as if sent,
        but takes no place in the send window."""
        self._open_unless_over(order, notional)

    def record_fill(self, order: Order, quantity: Decimal) -> None:
        """@brief `quantity` of `order` filled; a whole fill ends it."""
        key = str(order.client_order_id)
        over = order.status is OrderStatus.FILLED
        open_order = self._open.get(key)
        if open_order is None:
            filled, _ = self._early.get(key, (_ZERO, False))
            self._early[key] = (filled + quantity, over)
            return
        open_order.filled += quantity
        if over:
            del self._open[key]

    def record_end(self, order: Order) -> None:
        """@brief `order` is over without filling whole (cancelled, rejected,
        expired): it commits nothing any more."""
        key = str(order.client_order_id)
        if self._open.pop(key, None) is None:
            filled, _ = self._early.get(key, (_ZERO, False))
            self._early[key] = (filled, True)

    def _open_unless_over(self, order: Order, notional: Decimal) -> None:
        key = str(order.client_order_id)
        filled, over = self._early.pop(key, (_ZERO, False))
        if not over:
            self._open[key] = _OpenOrder(
                order.side, order.quantity, notional, order.reduce_only, filled
            )
