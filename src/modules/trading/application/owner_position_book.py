"""`EPIC-039D` — a Futures owner's book: what one budgeted owner has on the
venue right now, as a signed position.

@details The twin of `OwnerBook` (`EPIC-029` ADR D6) behind the same port
(`IOwnerBook`): the owner's open orders and send times (`OwnerOrderLedger`,
shared), and instead of an inventory a **signed position** with its average
entry, replayed from the owner's tagged fills (`OwnerPositionDeriver` at
registration, then each live fill, by `position_after`) and never supplied by
the owner. A fill is counted once by the exchange's trade id (`t`).

It is **cross-checked** with `positionRisk`, not replaced by it: `positionRisk`
is account-level and cannot tell the bot's position from one it did not open
(`DECISION` O11). `cross_check` names what differs by more than one step and
returns it once per cause:

- `POSITION_CHANGED_UNORDERED` - the exchange's amount moved since the last
  check while no tagged fill of the owner was applied (a forced close, an
  ADL, a trade by hand). It rests on `ORDER_TRADE_UPDATE` arriving before the
  `ACCOUNT_UPDATE` of the same trade, which the Futures fake assumes and no
  testnet run has yet verified (`EPIC-039L`).
- `POSITION_MISMATCH` - any other disagreement.

Neither changes the position: the exchange's figure is reported beside the
derived one and the guard (`EPIC-039F`) decides. Not thread-safe on its own:
`TradingSessionState` holds the books and calls them under its lock.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    nothing_counted,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_order_ledger import (
    OwnerOrderLedger,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_book import (
    IOwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
    OwnerBudget,
    OwnerBudgetFacts,
    OwnerInventory,
    PositionExposure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
    PositionDivergence,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_position_policy import (
    PositionFill,
    position_after,
)

_ZERO = Decimal(0)


class OwnerPositionBook(IOwnerBook):
    """One budgeted Futures owner's open orders, position and recent sends."""

    def __init__(
        self,
        registration: OwnerBudgetRegistration,
        position: OwnerPosition,
        step: Decimal,
        counted: Callable[[int | None], bool] = nothing_counted,
    ) -> None:
        """@param step The symbol's quantity step: a difference of no more
        than one step between the derived and the exchange's position is
        rounding, not a disagreement.
        @param counted Whether the fill with a trade id is already in
        `position` (the history it was derived from)."""
        if registration.budget.futures is None:
            raise ValueError("a Futures owner's budget declares Futures limits")
        if step <= 0:
            raise ValueError("a position's step is positive")
        self._registration = registration
        self._position = position
        self._step = step
        self._counted = counted
        #: The trade ids this book applied live, so a venue that reports one
        #: fill twice moves the position once.
        self._applied: set[int] = set()
        self._orders = OwnerOrderLedger(registration.budget.window)
        #: What `positionRisk` said at the last check, and how many fills were
        #: applied since: what tells a change the owner made from one it did not.
        self._last_exchange: Decimal | None = None
        self._fills_since_check = 0
        self._reported: tuple[Decimal, Decimal] | None = None

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
    def position(self) -> OwnerPosition:
        return self._position

    def facts_for(self, order: Order, now: datetime) -> OwnerBudgetFacts:
        orders = self._orders
        return OwnerBudgetFacts(
            budget=self.budget,
            open_order_count=orders.open_order_count,
            open_buy_quote=orders.open_buy_quote(),
            open_sell_quantity=orders.open_sell_quantity(),
            inventory=EMPTY_INVENTORY,
            time_since_last_order=orders.time_since_last_send(now),
            orders_in_window=orders.orders_in_window(now),
            order_side=order.side,
            order_quantity=order.quantity,
            position=PositionExposure(
                self._position,
                orders.open_adding_quantity(OrderSide.BUY),
                orders.open_adding_quantity(OrderSide.SELL),
                order.reduce_only,
            ),
        )

    def record_sent(self, order: Order, notional: Decimal, when: datetime) -> None:
        self._orders.record_sent(order, notional, when)

    def adopt_open(self, order: Order, notional: Decimal) -> None:
        self._orders.adopt_open(order, notional)

    def apply_fill(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None,
        trade_id: int | None = None,
    ) -> None:
        """@brief One fill of `order`: `fill` is `(price, quantity)` of this
        fill alone. A commission in the quote asset is added to the owner's
        fees; one in another asset is not converted. A fill the position
        already holds, from the history it was derived from or from an earlier
        report, changes nothing."""
        if trade_id is not None:
            if self._counted(trade_id) or trade_id in self._applied:
                return
            self._applied.add(trade_id)
        price, quantity = fill
        quote_fee = (
            fee[0] if fee is not None and fee[1] == BUDGET_QUOTE_ASSET else _ZERO
        )
        self._position = position_after(
            self._position, PositionFill(order.side, quantity, price, quote_fee)
        )
        self._fills_since_check += 1
        self._orders.record_fill(order, quantity)

    def apply_end(self, order: Order) -> None:
        self._orders.record_end(order)

    def held_inventory(self) -> OwnerInventory | None:
        return None

    def held_position(self) -> OwnerPosition | None:
        return self._position

    def cross_check(self, exchange_quantity: Decimal) -> PositionDivergence | None:
        derived = self._position.quantity
        moved_unordered = (
            self._last_exchange is not None
            and exchange_quantity != self._last_exchange
            and self._fills_since_check == 0
        )
        self._last_exchange = exchange_quantity
        self._fills_since_check = 0
        if abs(exchange_quantity - derived) <= self._step:
            self._reported = None
            return None
        cause = (derived, exchange_quantity)
        if cause == self._reported:
            return None
        self._reported = cause
        kind = (
            PositionDivergenceKind.POSITION_CHANGED_UNORDERED
            if moved_unordered
            else PositionDivergenceKind.POSITION_MISMATCH
        )
        return PositionDivergence(
            kind,
            self.owner_id,
            self._registration.tag,
            self.symbol,
            derived,
            exchange_quantity,
        )
