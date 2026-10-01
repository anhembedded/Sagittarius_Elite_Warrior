"""`EPIC-028O` — a Futures symbol's mark price, the price Binance values
positions and margin at."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_positive,
)


@dataclass(frozen=True)
class MarkPrice:
    """`GET /fapi/v1/premiumIndex`'s mark price for one symbol. Read for a
    flat symbol too, which `LivePosition.mark_price` cannot give."""

    symbol: str
    mark_price: Decimal
    #: When the exchange computed it.
    as_of: datetime

    def __post_init__(self) -> None:
        require_positive("mark_price", self.mark_price)
