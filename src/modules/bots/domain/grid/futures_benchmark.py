"""`EPIC-039K` — the benchmark of a position venue: holding what the grid opens.

@details See `futures_outcome.py`: the opening position held for the whole period, paying the
taker fee once and the same funding settlements; never liquidated.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_ZERO = Decimal(0)


@dataclass(slots=True)
class HoldBenchmark:
    """The opening quantity held from `start_price`, and what holding it has cost."""

    quantity: Decimal
    start_price: Decimal
    fee: Decimal = _ZERO
    funding: Decimal = _ZERO

    def value_at(self, capital: Decimal, price: Decimal) -> Decimal:
        return (
            capital
            + self.quantity * (price - self.start_price)
            - self.fee
            - self.funding
        )
