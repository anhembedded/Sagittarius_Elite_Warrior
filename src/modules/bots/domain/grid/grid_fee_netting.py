"""`BUG-212` — what a Spot buy leaves to sell: the one rule behind every SELL's quantity.

Spot takes a buy's fee from the base it buys, so a SELL of what a buy delivered is smaller than
the buy and rounded down to the step. The opening ladder's SELLs (`sells_net_of_opening_fee`),
the counter SELL a filled BUY owes (`grid_reactions._counter`) and the plan-time judgement of
both (`grid_order_sizing`) all call `sellable_after_buy`, so they cannot size it two ways.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)

_ROUNDING = OrderQuantityRoundingPolicy()


def sellable_after_buy(
    executed: Decimal, base_fee: Decimal, step_size: Decimal
) -> Decimal:
    """The quantity a buy of `executed` base, which paid `base_fee` in base, can sell."""
    return _ROUNDING.round_quantity_down(executed - base_fee, step_size)


def net_of_buy_fee(quantity: Decimal, fee: Decimal, step_size: Decimal) -> Decimal:
    """`sellable_after_buy` for a buy of `quantity` that paid the rate `fee` in base."""
    return sellable_after_buy(quantity, quantity * fee, step_size)
