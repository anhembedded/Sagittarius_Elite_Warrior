"""The fake Spot account's two small records: a fill and a balance (split from
`spot_account_state.py`, which sat at the 400-line ceiling)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class _Fill:
    price: Decimal
    qty: Decimal
    quote_amount: Decimal
    commission: Decimal
    commission_asset: str
    #: The exchange's id of this trade: the history lists it as `id`, and the
    #: stream's executionReport carries it as `"t"`, so a client can count the
    #: fill once however it learned of it.
    trade_id: int


class _Balance:
    __slots__ = ("free", "locked")

    def __init__(self, free: Decimal) -> None:
        self.free = free
        self.locked = Decimal(0)
