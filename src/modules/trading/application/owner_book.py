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
(`OwnerInventoryDeriver`) and kept current by the venue's emitter
(`VenueEventEmitter`), which each exchange record of a fill reaches: the
placement response, the user-data stream. It applies every fill and every end
here **before** the event reaches the bus. Not thread-safe on its own:
`TradingSessionState` holds the books and calls them under its lock.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_order_ledger import (
    OwnerOrderLedger,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_book import (
    IOwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerBudgetFacts,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
    PositionDivergence,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_inventory_policy import (
    OwnerFill,
    inventory_after,
)

_ZERO = Decimal(0)


def nothing_counted(_trade_id: int | None) -> bool:
    """The `counted` of a book whose inventory holds none of the venue's fills."""
    return False


class OwnerBook(IOwnerBook):
    """One budgeted owner's open orders, inventory and recent sends."""

    def __init__(
        self,
        registration: OwnerBudgetRegistration,
        inventory: OwnerInventory,
        counted: Callable[[int | None], bool] = nothing_counted,
    ) -> None:
        """@param counted Whether the fill with a trade id is already in
        `inventory`: a report of it that arrives later (the stream, after the
        history was read) is not counted a second time (`BUG-194`)."""
        self._registration = registration
        self._inventory = inventory
        self._counted = counted
        #: The trade ids this book applied live, so a venue that reports one
        #: fill twice moves the inventory once.
        self._applied: set[int] = set()
        self._orders = OwnerOrderLedger(registration.budget.window)

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
        orders = self._orders
        return OwnerBudgetFacts(
            budget=self.budget,
            open_order_count=orders.open_order_count,
            open_buy_quote=orders.open_buy_quote(),
            open_sell_quantity=orders.open_sell_quantity(),
            inventory=self.inventory,
            time_since_last_order=orders.time_since_last_send(now),
            orders_in_window=orders.orders_in_window(now),
            order_side=side,
            order_quantity=quantity,
        )

    def facts_for(self, order: Order, now: datetime) -> OwnerBudgetFacts:
        return self.facts(order.side, order.quantity, now)

    def held_inventory(self) -> OwnerInventory:
        return self._inventory

    def held_position(self) -> OwnerPosition | None:
        return None

    def agrees_with_last_report(self) -> bool:
        return False

    def cross_check(self, exchange_quantity: Decimal) -> PositionDivergence | None:
        """Spot has no position to compare: its inventory is checked against
        the venue's history when it is derived."""
        return None

    def record_sent(self, order: Order, notional: Decimal, when: datetime) -> None:
        """@brief `order` reached the venue at `when`; `notional` is the
        quote it commits (the preview's estimate). A fill or an end the
        venue already reported for it is taken into account."""
        self._orders.record_sent(order, notional, when)

    def adopt_open(self, order: Order, notional: Decimal) -> None:
        """@brief `order` was already resting on the venue when the budget
        was registered (a restart, a reconciliation): it commits as if sent,
        but takes no place in the send window."""
        self._orders.adopt_open(order, notional)

    def apply_fill(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None,
        trade_id: int | None = None,
    ) -> None:
        """@brief One fill of `order`: `fill` is `(price, quantity)` of this
        fill alone, `fee` its commission, `trade_id` the venue's id of it. A
        fee in the base asset leaves the owner holding less than it bought
        (ADR D6). A fill the inventory already holds, from the history it was
        derived from or from an earlier report, changes nothing."""
        if trade_id is not None:
            if self._counted(trade_id) or trade_id in self._applied:
                return
            self._applied.add(trade_id)
        price, quantity = fill
        base_fee = fee[0] if fee is not None and fee[1] == self._base_asset else _ZERO
        self._inventory = inventory_after(
            self._inventory, OwnerFill(order.side, quantity, price * quantity, base_fee)
        )
        self._orders.record_fill(order, quantity)

    def apply_end(self, order: Order) -> None:
        """@brief `order` is over without filling whole (cancelled, rejected,
        expired): it commits nothing any more."""
        self._orders.record_end(order)

    @property
    def _base_asset(self) -> str:
        return self._registration.base_asset
