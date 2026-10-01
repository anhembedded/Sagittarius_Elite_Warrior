"""`EPIC-028H` — what an order panel must know about one symbol on one venue
before it can size an order: the exchange's filters and the account's fee.

@details Read together because the panel needs both at the same moment (a
symbol chosen, a desk opened) and each is a network read on first use. The
rules are the same `SymbolOrderMetadata` every order is rounded with at
submit time, so the panel's quantities and the submitted ones agree.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)


@dataclass(frozen=True)
class OrderEntryTerms:
    """One symbol's order filters and the account's fee rates on it."""

    rules: SymbolOrderMetadata
    commission: CommissionRate
