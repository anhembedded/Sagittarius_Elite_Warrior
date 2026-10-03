"""`EPIC-029` ADR D6 — an owner budget: what a bot may have on the venue at
once, and how fast it may send.

@details A bot keeps a ladder of resting orders on one symbol, which the
four signal limits (`trading_limits.py`) refuse from the second order on:
they were written for one strategy entering one position at a time. A
budgeted owner's orders are judged against this budget instead, and against
the owner book trading keeps for it (`OwnerBudgetFacts`). The per-order
notional cap, the lease, the switch and the minimum notional still apply.

`OwnerBudgetCaps` (ADR O1) bounds what any budget may declare, so a bot that
asks for too much is refused at registration, naming the cap. The caps are
configuration (`ConfigKeys.TRADING_BOT_LIMITS_*`); the defaults are the
values the user approved on 2026-10-03, and they sit inside Binance Spot's
own `ORDERS` rate limits (the `EPIC-029A` implementation notes record them).

Plausible extensions, each a local change: a Futures owner (the inventory
becomes a position; one deriver behind the same registration), a daily
loss cap (one more field and one more check), a per-owner notional cap
(one field, consulted beside `max_notional_per_order`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ONE_MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class OwnerBudget:
    """What one owner may have on the venue at once, and how fast it may
    send. Every figure is a ceiling the owner's orders are checked against."""

    #: Open orders at once, counting the one being sent.
    max_open_orders: int
    #: Open BUY quote plus the inventory at cost, in the quote asset.
    max_exposure_quote: Decimal
    #: The shortest gap between two of the owner's orders.
    min_order_spacing: timedelta
    #: Orders inside any `window`, counting the one being sent.
    max_orders_per_window: int
    window: timedelta

    def __post_init__(self) -> None:
        if self.max_open_orders < 1 or self.max_orders_per_window < 1:
            raise ValueError("an owner budget allows at least one order")
        if self.max_exposure_quote <= 0:
            raise ValueError("an owner budget's exposure must be positive")
        if self.min_order_spacing < timedelta(0) or self.window <= timedelta(0):
            raise ValueError("an owner budget's spacing and window must be positive")


@dataclass(frozen=True)
class OwnerBudgetCaps:
    """ADR O1 — the most any owner budget may declare."""

    max_open_orders: int
    min_order_spacing: timedelta
    max_orders_per_minute: int

    def exceeded_by(self, budget: OwnerBudget) -> str | None:
        """@brief The name of the first cap `budget` declares beyond, or
        `None` when it fits all three.
        @details The rate is compared, not the raw count: 120 orders per two
        minutes is the same rate as 60 per minute, and 2 per second is not.
        """
        if budget.max_open_orders > self.max_open_orders:
            return "max_open_orders"
        if budget.min_order_spacing < self.min_order_spacing:
            return "min_order_spacing"
        if (
            budget.max_orders_per_window * _ONE_MINUTE
            > self.max_orders_per_minute * budget.window
        ):
            return "max_orders_per_minute"
        return None


#: The caps the user approved (ADR O1, 2026-10-03), used when the
#: configuration names none.
DEFAULT_OWNER_BUDGET_CAPS = OwnerBudgetCaps(
    max_open_orders=100,
    min_order_spacing=timedelta(milliseconds=250),
    max_orders_per_minute=60,
)


@dataclass(frozen=True)
class OwnerInventory:
    """The base an owner bought and still holds, net of base-asset fees, and
    what it cost in the quote asset. Derived from exchange evidence, never
    supplied by the owner (ADR D6)."""

    quantity: Decimal
    cost: Decimal


EMPTY_INVENTORY = OwnerInventory(Decimal(0), Decimal(0))


@dataclass(frozen=True)
class OwnerBudgetFacts:
    """What `TradingLimitPolicy` judges a budgeted owner's order against:
    the budget, the owner book as it stands, and the order being sent."""

    budget: OwnerBudget
    open_order_count: int
    #: The quote the owner's open BUY orders commit.
    open_buy_quote: Decimal
    #: The base the owner's open SELL orders commit.
    open_sell_quantity: Decimal
    inventory: OwnerInventory
    #: `None` when the owner has sent nothing this session.
    time_since_last_order: timedelta | None
    #: The owner's orders inside the budget's window, before this one.
    orders_in_window: int
    order_side: OrderSide
    order_quantity: Decimal
