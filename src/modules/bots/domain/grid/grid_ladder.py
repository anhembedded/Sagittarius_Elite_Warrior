"""`EPIC-029E` — turning a plan into a live ladder, and back into a plan.

· `runtime_from_plan` — the runtime a start begins with: every level EMPTY,
  each with its `buy_quantity` (its share of the capital at its own price,
  rounded down to the step).
· `ladder_orders` — the orders the start sequence places after the opening
  buy (ADR §3.1): **outward from the last price**, nearest first, so the
  levels most likely to fill soonest are resting first. The level the plan
  left EMPTY stays empty.
· `resized_for_inventory` — the plan a resume proposes (ADR D13, §3.4): the
  SELL side sized to the inventory the bot actually holds, nearest first,
  and **no opening buy**. A SELL level the inventory does not reach, or
  reaches with less than the exchange's NOTIONAL minimum, is left EMPTY. The user confirms this plan before anything is placed (O2).
· `buys_within_capital` — a resume's BUY side shares only the capital the
  inventory leaves (`EPIC-035R`): trading refuses open BUYs plus the inventory
  at cost beyond `capital_quote`, so a BUY side sized from the whole capital
  again, after the bot bought down the ladder, asks for what the budget refuses.
  A share under the exchange's NOTIONAL minimum leaves its level EMPTY.
· `unplaced_inventory` — the inventory the SELL levels do not reach, which a
  resume names to the user instead of keeping in silence.
· `sells_net_of_opening_fee` — the plan a start lays after its opening buy:
  on Spot a buy's fee is taken from the base it buys, so the opening receives
  `quantity × (1 − taker)` and each SELL level is shrunk by the fee, rounded
  down to the step. Sized to the gross quantity, the last SELL would ask to
  sell base the bot never received (`owner_budget_sell_exceeds_inventory`).
· `crossed_exit` — which exit a price crosses (ADR D11): at or below the
  stop loss, at or above the take profit.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridLevel,
    GridPlan,
    LevelSide,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
    PlaceOrder,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ROUNDING = OrderQuantityRoundingPolicy()
_ZERO = Decimal(0)


def runtime_from_plan(plan: GridPlan, step_size: Decimal) -> GridRuntime:
    """A fresh ladder for `plan`: every level EMPTY, none placed yet."""
    return GridRuntime(
        tuple(
            RuntimeLevel(
                level.index,
                level.price,
                _ROUNDING.round_quantity_down(
                    plan.capital_per_level / level.price, step_size
                ),
            )
            for level in plan.levels
        ),
        start_price=plan.last_price,
    )


def ladder_orders(plan: GridPlan) -> tuple[PlaceOrder, ...]:
    """The plan's resting orders, nearest the last price first."""
    ordered = sorted(
        plan.order_levels,
        key=lambda level: (abs(level.price - plan.last_price), level.index),
    )
    return tuple(_order_for(level) for level in ordered if level.quantity > 0)


def resized_for_inventory(
    plan: GridPlan, inventory: Decimal, min_notional: Decimal
) -> GridPlan:
    """`plan` with its SELL side sized to `inventory` and no opening buy; a
    level the inventory would fill to less than `min_notional` stays EMPTY."""
    remaining = inventory
    resized: dict[int, GridLevel] = {}
    for level in sorted(plan.sell_levels, key=lambda lv: lv.price):
        quantity = min(level.quantity, remaining)
        if quantity * level.price < min_notional:
            quantity = _ZERO
        remaining -= quantity
        side = LevelSide.SELL if quantity > 0 else LevelSide.EMPTY
        resized[level.index] = replace(level, side=side, quantity=quantity)
    levels = tuple(resized.get(level.index, level) for level in plan.levels)
    return replace(plan, levels=levels, opening_buy_quantity=_ZERO)


def buys_within_capital(plan: GridPlan, left: Decimal, rules: LadderRules) -> GridPlan:
    """`plan` with its BUY levels sharing `left` of the quote, never more than
    their planned share each; a level whose share would be worth less than the
    NOTIONAL minimum stays EMPTY. A `left` at or below zero leaves no BUY."""
    buys = plan.buy_levels
    if not buys:
        return plan
    share = min(plan.capital_per_level, max(left, _ZERO) / len(buys))
    resized: dict[int, GridLevel] = {}
    for level in buys:
        quantity = _ROUNDING.round_quantity_down(share / level.price, rules.step_size)
        if quantity * level.price < rules.min_notional:
            quantity = _ZERO
        side = LevelSide.BUY if quantity > 0 else LevelSide.EMPTY
        resized[level.index] = replace(level, side=side, quantity=quantity)
    return replace(plan, levels=tuple(resized.get(lv.index, lv) for lv in plan.levels))


def unplaced_inventory(plan: GridPlan, inventory: Decimal) -> Decimal:
    """The base the plan's SELL levels leave unsold: `inventory` beyond them."""
    return max(inventory - sum((lv.quantity for lv in plan.sell_levels), _ZERO), _ZERO)


def sells_net_of_opening_fee(
    plan: GridPlan, taker_fee: Decimal, step_size: Decimal
) -> GridPlan:
    """`plan` with each SELL level sized to its share net of the buy's fee."""
    kept = 1 - taker_fee
    levels = tuple(
        replace(
            level,
            quantity=_ROUNDING.round_quantity_down(level.quantity * kept, step_size),
        )
        if level.side is LevelSide.SELL
        else level
        for level in plan.levels
    )
    return replace(plan, levels=levels)


def crossed_exit(
    price: Decimal, stop_loss: Decimal | None, take_profit: Decimal | None
) -> GridReason | None:
    """`STOP_LOSS` or `TAKE_PROFIT` when `price` reached one, else `None`."""
    return crossed_exit_in_range(price, price, stop_loss, take_profit)


def crossed_exit_in_range(
    low: Decimal,
    high: Decimal,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
) -> GridReason | None:
    """`STOP_LOSS` when `low` reached the stop, else `TAKE_PROFIT` when `high`
    reached the take profit (`BUG-191`): a range traded, not only a price."""
    if stop_loss is not None and low <= stop_loss:
        return GridReason.STOP_LOSS
    if take_profit is not None and high >= take_profit:
        return GridReason.TAKE_PROFIT
    return None


def _order_for(level: GridLevel) -> PlaceOrder:
    side = OrderSide.SELL if level.side is LevelSide.SELL else OrderSide.BUY
    return PlaceOrder(level.index, side, level.price, level.quantity)
