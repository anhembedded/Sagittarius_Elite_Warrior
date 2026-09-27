"""`EPIC-027M` — how much of one Spot asset Emergency Stop may sell.

@details The Spot analogue of a Futures `LivePosition` to close: instead of
a signed `position_amt` this app opened itself, a Spot holding is a single
non-negative quantity that may already have existed before this app ever
enabled trading (ADR: the baseline the app owns only the difference it
created). This policy answers exactly one question — given what the
account holds now and what the baseline held, how much is this app's own
surplus to sell — and answers it as a pure function so it can be
mutation-verified in isolation from `EmergencyStopCommandHandler`'s network
calls and error handling.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)

_ROUNDING_POLICY = OrderQuantityRoundingPolicy()


def sellable_spot_quantity(
    current_total: Decimal, baseline_quantity: Decimal, step_size: Decimal
) -> Decimal:
    """@brief The quantity of one asset Emergency Stop may sell: whatever
    the account holds now beyond what the baseline already held, floored to
    the exchange's lot step.
    @details Never negative — a holding that shrank below its own baseline
    (the user sold some by hand outside this app, or a fee was taken from
    it) has nothing left for this app to sell; `EPIC-027M`'s own acceptance
    criterion is that Emergency Stop never sells what the baseline held, so
    zero, not a negative "quantity to buy back", is the only correct answer
    here. `step_size` flooring is the same `LOT_SIZE`/`MARKET_LOT_SIZE`
    rounding every other order in this app already goes through
    (`OrderQuantityRoundingPolicy`) — a surplus smaller than one step floors
    to zero, which the caller reports as dust rather than an order.
    """
    surplus = current_total - baseline_quantity
    if surplus <= 0:
        return Decimal(0)
    return _ROUNDING_POLICY.round_quantity_down(surplus, step_size)
