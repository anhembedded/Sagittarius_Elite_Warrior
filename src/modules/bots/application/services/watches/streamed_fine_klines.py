"""`EPIC-029D` — 1-second klines read once, front to back, a candle at a time.

The replay asks for each reactive candle's klines in time order
(`FineKlines.within`). This source walks one repository stream alongside it:
klines before the asked candle are dropped unread, the candle's own are
returned, and the first kline past it is kept for the next ask. Memory holds
one candle's klines, never the week.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.fine_klines import (
    FineKlines,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
)


def price_bar(candle: MarketData) -> PriceBar:
    """A stored candle in the bots module's terms (floats read as written)."""
    return PriceBar(
        candle.open_time,
        Decimal(str(candle.open_price)),
        Decimal(str(candle.high_price)),
        Decimal(str(candle.low_price)),
        Decimal(str(candle.close_price)),
    )


class StreamedFineKlines(FineKlines):
    """@brief A forward-only window over one stream of 1-second klines."""

    def __init__(self, stream: Iterator[MarketData]) -> None:
        self._stream = stream
        self._next: MarketData | None = None
        self._exhausted = False

    def within(self, start: datetime, end: datetime) -> tuple[PriceBar, ...]:
        found: list[PriceBar] = []
        while (kline := self._peek()) is not None and kline.open_time < end:
            self._next = None
            if kline.open_time >= start:
                found.append(price_bar(kline))
        return tuple(found)

    def _peek(self) -> MarketData | None:
        if self._next is None and not self._exhausted:
            self._next = next(self._stream, None)
            self._exhausted = self._next is None
        return self._next
