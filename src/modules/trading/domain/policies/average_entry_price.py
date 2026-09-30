"""`EPIC-028E` — the average entry price of a Spot holding, from its fills.

@details Average-cost method, oldest fill first:

- a **buy** adds the base quantity received and the quote paid. A fee
  charged in the base asset (Spot's default for a buy) reduces what was
  received; one charged in the quote asset adds to what was paid;
- a **sell** removes base quantity at the current average cost, so it lowers
  the cost basis without changing the average. A fee charged in the base
  asset adds to what left the account.

A fee charged in a third asset (BNB, when the account pays fees that way) is
left out of the cost: pricing it would need a BNB price at the time of the
fill, which the fills do not carry. The average is then slightly low, by the
BNB fees alone; this is stated here rather than hidden in a guessed price.

**Only answers when the fills explain the holding.** Anything the fills do
not show — coins bought before `since`, a deposit, a transfer from Futures —
leaves the replayed quantity different from what the account holds, and the
answer is `None`. So is a sell of more than the fills ever bought, which
means the same thing. `tolerance` absorbs the dust Binance's own rounding
leaves (the holding's `dust_threshold`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.average_entry_price import (
    AverageEntryPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


@dataclass(frozen=True)
class HeldPair:
    """The pair the fills are on and what the account holds of it now."""

    symbol: str
    base_asset: str
    quote_asset: str
    held_quantity: Decimal
    tolerance: Decimal


def average_entry_price(
    fills: Iterable[TradeRecord], held: HeldPair
) -> AverageEntryPrice | None:
    """@return The average cost of `held.held_quantity`, or `None` when the
    fills do not account for it (see the module docstring)."""
    quantity = Decimal(0)
    cost = Decimal(0)
    for fill in sorted(fills, key=lambda record: (record.time, record.trade_id)):
        base_fee = fill.fee if fill.fee_asset == held.base_asset else Decimal(0)
        quote_fee = fill.fee if fill.fee_asset == held.quote_asset else Decimal(0)
        if fill.side is OrderSide.BUY:
            quantity += fill.quantity - base_fee
            cost += fill.quote_quantity + quote_fee
            continue
        sold = fill.quantity + base_fee
        if sold > quantity:
            return None
        cost -= cost * sold / quantity
        quantity -= sold
    if quantity <= 0 or abs(quantity - held.held_quantity) > held.tolerance:
        return None
    return AverageEntryPrice(
        symbol=held.symbol, price=cost / quantity, quantity=quantity
    )
