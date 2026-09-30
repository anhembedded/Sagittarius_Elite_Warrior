"""`EPIC-028E` — what a Spot holding cost on average (closes `EPIC-027` ADR O6).

@details Spot has no position and so no entry price: Binance reports balances
only (ADR D7). The average entry price is rebuilt from the account's own
fills (`GET /api/v3/myTrades`, ADR O6) by `average_entry_price` in
`domain/policies/`. This type is what that rebuild answers when it can; when
it cannot, the answer is `None`, never an estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AverageEntryPrice:
    """The average cost per unit of the base asset now held on `symbol`."""

    symbol: str
    #: Quote asset per base unit, fees paid in either asset included.
    price: Decimal
    #: The quantity the fills account for; equal to the holding it was
    #: checked against, within that holding's dust threshold.
    quantity: Decimal
