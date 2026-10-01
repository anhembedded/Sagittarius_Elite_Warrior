"""`EPIC-028G` — what both desks' order estimates share.

@details The fee is one formula on both venues; the cost and the maximum are
not (`futures_order_estimates.py` follows Binance's USD-M margin rules,
`spot_order_estimates.py` the Spot balance). What they do share is here:

- `estimated_fee`: quantity × price × fee rate. The rate is the taker rate
  (a market order pays it); a negative rate (a maker rebate) is refused,
  because a rebate is never certain before the fill;
- `largest_fitting_quantity`: the largest multiple of the lot step whose cost
  at a fixed cost per unit stays within a budget. Both maxima end here, so
  the rounding lives in one place.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_not_negative,
    require_positive,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)

_ROUNDING = OrderQuantityRoundingPolicy()


def estimated_fee(quantity: Decimal, price: Decimal, fee_rate: Decimal) -> Decimal:
    """@return The fee an order of `quantity` at `price` pays, in the quote
    asset."""
    require_not_negative("quantity", quantity)
    require_positive("price", price)
    require_not_negative("fee_rate", fee_rate)
    return quantity * price * fee_rate


def largest_fitting_quantity(
    unit_cost: Decimal, budget: Decimal, step_size: Decimal
) -> Decimal:
    """@return The largest multiple of `step_size` whose cost at `unit_cost`
    per unit does not exceed `budget`; zero when one step does not fit.
    @details The division is rounded to `Decimal`'s precision, which can land
    one step off either way at the boundary (the PR #300 review measured the
    undershoot); the result is corrected by one step against the product, so
    within the context's 28 significant digits the step above never fits and
    the answer itself always does."""
    require_positive("unit_cost", unit_cost)
    require_not_negative("budget", budget)
    require_positive("step_size", step_size)
    quantity = _ROUNDING.round_quantity_down(budget / unit_cost, step_size)
    if quantity * unit_cost > budget:
        return quantity - step_size
    if (quantity + step_size) * unit_cost <= budget:
        return quantity + step_size
    return quantity
