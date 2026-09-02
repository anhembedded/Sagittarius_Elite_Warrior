"""`EPIC-021C` — order quantity/price rounding, as its own domain policy.

@details Same shelf as `domain/backtesting/policies/`'s
`OrderMatchingPolicy`/`FeeCalculatorPolicy`/`MarginRiskPolicy`, but
deliberately NOT under `backtesting/`: this is exchange-agnostic order
construction logic a live order path needs too, not something scoped to
simulation. This is the logic that decides which order is even valid to
send — get it wrong and every live order fails with Binance's `-1013`
*after* being sent, which is a worse failure mode than catching it here
first.

`Decimal` throughout, never `float` — see `FuturesSymbolMetadata`'s own
docstring for why.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide


class NotionalCheck(str, Enum):
    """A named decision, not a bare `bool` wandering the codebase
    unexplained — the whole point of `is_notional_sufficient()`'s return
    type."""

    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class OrderQuantityRoundingPolicy:
    """@brief Domain policy for rounding an order's quantity/price to what
    the exchange will actually accept, and checking its minimum notional.
    """

    def round_quantity_down(self, quantity: Decimal, step_size: Decimal) -> Decimal:
        """@brief Rounds `quantity` down to the nearest multiple of
        `step_size`.
        @details Always down, never to the nearest step: rounding up could
        submit an order larger than the capital/margin it was sized for and
        get rejected outright; rounding down only ever makes the order
        smaller than intended, never invalid on that axis. `step_size <= 0`
        returns `quantity` unchanged — no exchange filter to round against.
        """
        if step_size <= 0:
            return quantity
        steps = (quantity / step_size).to_integral_value(rounding=ROUND_FLOOR)
        return steps * step_size

    def round_price_to_tick(
        self, price: Decimal, tick_size: Decimal, side: OrderSide
    ) -> Decimal:
        """@brief Rounds `price` to the nearest multiple of `tick_size`, in
        the direction that favours getting filled.
        @details A BUY that rounds up could pay more than intended, so BUY
        rounds down; a SELL that rounds down could receive less than
        intended, so SELL rounds up. `tick_size <= 0` returns `price`
        unchanged.
        """
        if tick_size <= 0:
            return price
        rounding = ROUND_FLOOR if side is OrderSide.BUY else ROUND_CEILING
        steps = (price / tick_size).to_integral_value(rounding=rounding)
        return steps * tick_size

    def is_notional_sufficient(
        self, quantity: Decimal, price: Decimal, min_notional: Decimal
    ) -> NotionalCheck:
        """@brief Whether `quantity * price` clears the exchange's minimum
        order value."""
        notional = quantity * price
        if notional >= min_notional:
            return NotionalCheck.SUFFICIENT
        return NotionalCheck.INSUFFICIENT
