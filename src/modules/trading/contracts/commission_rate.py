"""`EPIC-028F` — what one venue charges on one symbol, as the exchange says."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CommissionRate:
    """Maker and taker rates as fractions of the traded notional: `0.001`
    is 0.1 %. Read from the exchange, never assumed from a published fee
    table, because an account's tier and any discount change them. A maker
    rate can be negative (a rebate some tiers earn), so no sign is
    enforced."""

    symbol: str
    maker: Decimal
    taker: Decimal
