"""`EPIC-028O` — the best bid and ask on a symbol's book."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_not_negative,
)


@dataclass(frozen=True)
class BestBidAsk:
    """`GET .../ticker/bookTicker` for one symbol, on either venue. A side
    with no order reads as a zero price and quantity, as Binance sends it;
    `has_bid` and `has_ask` say whether there is one."""

    symbol: str
    bid_price: Decimal
    bid_quantity: Decimal
    ask_price: Decimal
    ask_quantity: Decimal

    def __post_init__(self) -> None:
        for name in ("bid_price", "bid_quantity", "ask_price", "ask_quantity"):
            require_not_negative(name, getattr(self, name))

    @property
    def has_bid(self) -> bool:
        return self.bid_price > 0 and self.bid_quantity > 0

    @property
    def has_ask(self) -> bool:
        return self.ask_price > 0 and self.ask_quantity > 0
