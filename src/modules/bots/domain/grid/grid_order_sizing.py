"""`BUG-212` — the one place the orders a Grid sends are sized, for the judgement and the run.

The pre-start check and the executor used to size a SELL two ways: the check took the level's
notional less the fee, the executor floored the quantity to the step after the fee. The owner's
35 USDT plan passed the check with a 5.03 USDT order that the executor then sent as 0.0020 ETH,
4.79 USDT, under Binance's 5 USDT minimum, after the opening market buy had been spent.

Both now ask this module:

  · `opening_ladder` — the plan the start lays after its opening buy: on Spot every SELL net of
    the opening's fee and floored to the step (`sells_net_of_opening_fee`); a position venue's
    ladder as planned, its fee is paid in quote;
  · `sized_orders` — every order that ladder sends and the first counter order of every pair of
    neighbouring levels (a BUY at the lower level after the upper one sells, a SELL net of the fee
    at the upper level after the lower one buys), so a plan that starts also cycles;
  · `find_breach` — the smallest of them when it is under the exchange's NOTIONAL minimum, or
    rounds to nothing, with the capital that would clear it. The check refuses with it before
    Start; the executor refuses with the same value before it spends anything.

Not covered, by design: a counter sized from a partial fill is sized by `grid_reactions` from what
filled and dropped when under the minimum (`_settle_short`); the exchange's `minQty` is not part of
`ExchangeTerms` (the minimum notional is the binding filter at every price the bots trade).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, Decimal
from enum import Enum
from itertools import pairwise

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    net_of_buy_fee,
    runtime_from_plan,
    sells_net_of_opening_fee,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSide,
    LevelSizing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    plan as plan_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_CENT = Decimal("0.01")
_ZERO = Decimal(0)
#: How much dearer each retry of the capital search is; quantity rounding moves the answer by
#: a step, so the proportional estimate is nudged until the real sizing agrees.
_SEARCH_GROWTH = Decimal("1.002")
_SEARCH_TRIES = 200


class OrderOrigin(str, Enum):
    """Why the order is sent."""

    #: Laid by the start, after the opening buy.
    START = "start"
    #: Sent when a neighbour fills, and sized from the level's own share.
    COUNTER = "counter"


@dataclass(frozen=True, slots=True)
class SizedOrder:
    """One order as the executor will send it."""

    level_index: int
    side: OrderSide
    price: Decimal
    quantity: Decimal
    origin: OrderOrigin

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity

    @property
    def label(self) -> str:
        counter = " counter" if self.origin is OrderOrigin.COUNTER else ""
        return f"L{self.level_index}{counter} {self.side.value}"


@dataclass(frozen=True, slots=True)
class MinimumBreach:
    """The smallest order of a plan, which the exchange would refuse."""

    order: SizedOrder
    minimum: Decimal
    #: A capital whose plan clears the minimum; `None` when none was found.
    minimum_capital: Decimal | None

    def text(self, base_asset: str, quote_asset: str) -> str:
        """The refusal in the user's words: the order, its worth, the minimum, what to change."""
        base, quote = base_asset or "base", quote_asset or "quote"
        order = self.order
        what = (
            f"{order.label} order rounds to nothing at the exchange's quantity step"
            if order.quantity == 0
            else f"{order.label} order of {order.quantity:f} {base} at {order.price:f} "
            f"is worth {order.notional:.2f} {quote}"
        )
        change = (
            f"raise the capital to about {self.minimum_capital} {quote} or use fewer grids"
            if self.minimum_capital is not None
            else "raise the capital or use fewer grids"
        )
        return (
            f"{what}, below the exchange minimum of {self.minimum:f} {quote}; {change}"
        )


def opening_ladder(plan: GridPlan, terms: ExchangeTerms) -> GridPlan:
    """The ladder a start lays once its opening is taken."""
    if plan.level_sizing is LevelSizing.EQUAL_QUANTITY:
        return plan
    return sells_net_of_opening_fee(plan, terms.taker_fee, terms.step_size)


def sized_orders(plan: GridPlan, terms: ExchangeTerms) -> tuple[SizedOrder, ...]:
    """Every order the start lays, then each level pair's first counter order."""
    started = tuple(
        SizedOrder(
            level.index,
            OrderSide.SELL if level.side is LevelSide.SELL else OrderSide.BUY,
            level.price,
            level.quantity,
            OrderOrigin.START,
        )
        for level in opening_ladder(plan, terms).order_levels
    )
    return started + _counters(plan, terms)


def smallest_order(plan: GridPlan, terms: ExchangeTerms) -> SizedOrder | None:
    """The order of least worth that `plan` sends, or `None` for a plan with none."""
    return min(sized_orders(plan, terms), key=lambda o: o.notional, default=None)


def find_breach(
    params: GridParams, plan: GridPlan, terms: ExchangeTerms
) -> MinimumBreach | None:
    """The smallest order under the minimum, with the capital that clears it.

    The orders the start lays are judged before the counters: they are what stops the
    opening, so they are what the user is told about first."""
    orders = sized_orders(plan, terms)
    for origin in OrderOrigin:
        smallest = min(
            (o for o in orders if o.origin is origin),
            key=lambda o: o.notional,
            default=None,
        )
        if smallest is not None and smallest.notional < terms.min_notional:
            return MinimumBreach(
                smallest,
                terms.min_notional,
                _capital_clearing(params, plan, terms, smallest),
            )
    return None


def _counters(plan: GridPlan, terms: ExchangeTerms) -> tuple[SizedOrder, ...]:
    fee = _ZERO if plan.level_sizing is LevelSizing.EQUAL_QUANTITY else terms.taker_fee
    shares = runtime_from_plan(plan, terms.step_size).levels
    orders: list[SizedOrder] = []
    for lower, upper in pairwise(plan.levels):
        bought = shares[lower.index].buy_quantity
        orders.append(
            SizedOrder(
                lower.index, OrderSide.BUY, lower.price, bought, OrderOrigin.COUNTER
            )
        )
        orders.append(
            SizedOrder(
                upper.index,
                OrderSide.SELL,
                upper.price,
                net_of_buy_fee(bought, fee, terms.step_size),
                OrderOrigin.COUNTER,
            )
        )
    return tuple(orders)


def _capital_clearing(
    params: GridParams, plan: GridPlan, terms: ExchangeTerms, smallest: SizedOrder
) -> Decimal | None:
    """The smallest capital, searched upward from the proportional estimate, whose plan sends
    nothing under the minimum."""
    if smallest.notional <= 0:
        return None
    capital = (params.capital_quote * terms.min_notional / smallest.notional).quantize(
        _CENT, rounding=ROUND_CEILING
    )
    for _ in range(_SEARCH_TRIES):
        retried = plan_for(
            replace(params, capital_quote=capital),
            terms,
            plan.last_price,
            plan.level_sizing,
        )
        found = smallest_order(retried, terms)
        if found is None or found.notional >= terms.min_notional:
            return capital
        capital = max(
            capital + _CENT,
            (capital * _SEARCH_GROWTH).quantize(_CENT, rounding=ROUND_CEILING),
        )
    return None
