"""`EPIC-029D` — the benchmark every Grid result is shown against (ADR D18).

The same capital spent at the first candle's open, in one market buy at the
taker fee, then held: on Spot the fee comes out of the base bought, so the
position is `capital / open × (1 − taker)`, rounded down to the step. A grid
that trails this line in an uptrend is the report's expected outcome, not a
defect, and the comparison is what lets the user see it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)

_ROUNDING = OrderQuantityRoundingPolicy()


@dataclass(frozen=True, slots=True)
class BuyAndHold:
    """The base bought at the start and the quote left over."""

    quantity: Decimal
    cash: Decimal

    def value_at(self, price: Decimal) -> Decimal:
        return self.cash + self.quantity * price


def buy_and_hold(
    capital: Decimal, open_price: Decimal, taker_fee: Decimal, step_size: Decimal
) -> BuyAndHold:
    """`capital` spent at `open_price`, net of the taker fee taken in base."""
    bought = _ROUNDING.round_quantity_down(capital / open_price, step_size)
    received = _ROUNDING.round_quantity_down(bought * (1 - taker_fee), step_size)
    return BuyAndHold(received, capital - bought * open_price)
