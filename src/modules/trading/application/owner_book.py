"""`EPIC-029` ADR D6 — the owner book: what one budgeted owner has on the
venue right now.

@details Trading keeps one per budgeted owner, so the owner's next order is
judged against the venue's evidence, never against the owner's own account
of itself. It holds three things:

- the owner's open orders, by client order id, with what each still
  commits (the BUY quote, or the SELL base);
- the inventory: the base the owner bought and still holds, net of
  base-asset fees, with its cost (average cost: a sell takes its share of
  the cost with it);
- the send times inside the budget's window, and the last one.

It is seeded with an inventory derived from exchange history
(`OwnerInventoryDeriver`) and kept current by the venue's user-data path,
which applies every fill and every end here **before** the event reaches
the bus (`VenueEventEmitter`). Not thread-safe on its own:
`TradingSessionState` holds the books and calls them under its lock.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerBudgetFacts,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_inventory_policy import (
    OwnerFill,
    inventory_after,
)

_ZERO = Decimal(0)


@dataclass
class _OpenOrder:
    side: OrderSide
    #: The base the order was sent for; zero for a quote-sized market buy.
    quantity: Decimal
    #: What it commits when nothing has filled: the BUY's notional.
    notional: Decimal
    filled: Decimal = _ZERO

    @property
    def remaining(self) -> Decimal:
        return self.quantity - self.filled

    @property
    def committed_quote(self) -> Decimal:
        """A BUY's quote still at stake. A quote-sized buy (no base
        quantity) commits its whole quote until it ends."""
        if self.side is not OrderSide.BUY:
            return _ZERO
        if self.quantity == 0:
            return self.notional
        return self.notional * self.remaining / self.quantity


class OwnerBook:
    """One budgeted owner's open orders, inventory and recent sends."""

    def __init__(
        self, registration: OwnerBudgetRegistration, inventory: OwnerInventory
    ) -> None:
        self._registration = registration
        self._inventory = inventory
        self._open: dict[str, _OpenOrder] = {}
        self._sends: deque[datetime] = deque()

    @property
    def owner_id(self) -> str:
        return self._registration.owner_id

    @property
    def symbol(self) -> str:
        return self._registration.symbol

    @property
    def budget(self) -> OwnerBudget:
        return self._registration.budget

    @property
    def inventory(self) -> OwnerInventory:
        return self._inventory

    def facts(
        self, side: OrderSide, quantity: Decimal, now: datetime
    ) -> OwnerBudgetFacts:
        """@brief What `TradingLimitPolicy` judges an order of `side` and
        `quantity`, sent at `now`, against."""
        horizon = now - self.budget.window
        last = self._sends[-1] if self._sends else None
        return OwnerBudgetFacts(
            budget=self.budget,
            open_order_count=len(self._open),
            open_buy_quote=sum(
                (order.committed_quote for order in self._open.values()), _ZERO
            ),
            open_sell_quantity=sum(
                (
                    order.remaining
                    for order in self._open.values()
                    if order.side is OrderSide.SELL
                ),
                _ZERO,
            ),
            inventory=self.inventory,
            time_since_last_order=None if last is None else now - last,
            orders_in_window=sum(1 for sent in self._sends if sent > horizon),
            order_side=side,
            order_quantity=quantity,
        )

    def record_sent(self, order: Order, notional: Decimal, when: datetime) -> None:
        """@brief `order` reached the venue at `when`; `notional` is the
        quote it commits (the preview's estimate)."""
        self._open[str(order.client_order_id)] = _OpenOrder(
            order.side, order.quantity, notional
        )
        self._sends.append(when)
        self._forget_sends_before(when)

    def apply_fill(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None,
    ) -> None:
        """@brief One fill of `order`: `fill` is `(price, quantity)` of this
        fill alone, `fee` its commission. A fee in the base asset leaves the
        owner holding less than it bought (ADR D6)."""
        price, quantity = fill
        base_fee = fee[0] if fee is not None and fee[1] == self._base_asset else _ZERO
        self._inventory = inventory_after(
            self._inventory, OwnerFill(order.side, quantity, price * quantity, base_fee)
        )
        key = str(order.client_order_id)
        open_order = self._open.get(key)
        if open_order is not None:
            open_order.filled += quantity
        if order.status is OrderStatus.FILLED:
            self._open.pop(key, None)

    def apply_end(self, order: Order) -> None:
        """@brief `order` is over without filling whole (cancelled, rejected,
        expired): it commits nothing any more."""
        self._open.pop(str(order.client_order_id), None)

    @property
    def _base_asset(self) -> str:
        return self._registration.base_asset

    def _forget_sends_before(self, now: datetime) -> None:
        horizon = now - self.budget.window
        while self._sends and self._sends[0] <= horizon:
            self._sends.popleft()
