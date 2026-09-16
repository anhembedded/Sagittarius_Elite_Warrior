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

@par Why it sits in `contracts/` rather than `domain/policies/`
`EPIC-025` PR 2.1d, on the same measurement PR 2.1a used to publish
`OrderIntent`: what a module's `contracts/` holds is what crosses its boundary,
and this file already did. `contracts/order_preview.py` — a published DTO — has
a `notional_check: NotionalCheck` field, so a consumer reading that answer had
to import the enum out of this module's `domain/`; and two callers outside the
module (`presentation/cli/order_preview_formatter.py` and, since PR 2.1d,
`strategy`'s own `position_sizing_bridge`) name the policy itself. It is also
the half of order construction that carries no trading decision: what the
exchange will accept is a filter, not a judgement about whether to trade — that
is `TradingLimitPolicy`, which stays in `domain/policies/` where nothing
outside the module may reach it. ADR D17 draws the same line from the other
side: `strategy` decides how much capital to commit, `trading` owns what the
venue accepts, so the rounding rule has to be reachable from `strategy`
*without* a boundary violation, and publishing what already crossed is the
answer rather than a second copy of `ROUND_FLOOR`.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


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
