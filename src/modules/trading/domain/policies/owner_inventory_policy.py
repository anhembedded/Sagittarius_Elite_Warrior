"""`EPIC-029` ADR D6 — how one fill moves an owner's inventory.

@details One formula, used by the owner book as fills arrive and by the
deriver as it replays the venue's history, so the two can never disagree:

- a BUY adds the base bought, less any fee charged in the base asset, and
  adds the quote paid to the cost;
- a SELL takes out the base sold plus any base-asset fee, and takes the same
  share of the cost with it (average cost);
- once nothing is held, nothing is left at cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

_ZERO = Decimal(0)


@dataclass(frozen=True)
class OwnerFill:
    """One fill of an owner's order, as inventory sees it."""

    side: OrderSide
    #: The base this fill traded.
    quantity: Decimal
    #: The quote it traded for.
    quote: Decimal
    #: The part of its fee charged in the base asset; zero otherwise.
    base_fee: Decimal


def inventory_after(inventory: OwnerInventory, fill: OwnerFill) -> OwnerInventory:
    """@brief `inventory` once `fill` has happened."""
    if fill.side is OrderSide.BUY:
        return OwnerInventory(
            inventory.quantity + fill.quantity - fill.base_fee,
            inventory.cost + fill.quote,
        )
    sold = fill.quantity + fill.base_fee
    held = inventory.quantity
    cost = inventory.cost
    if held > 0:
        cost -= cost * min(sold, held) / held
    remaining = held - sold
    return OwnerInventory(remaining, cost if remaining > 0 else _ZERO)
