"""`EPIC-029D` — where a replay gets each candle's 1-second klines.

A week of BTCUSDT is about 600,000 one-second klines, too many to hold at once.
The replay asks for them a candle at a time, oldest candle first, and only for
a candle a resting order or an exit could react to. A source can therefore
stream the whole range once, front to back, keeping one candle's klines in
memory.

Recipes (each is one implementation of `FineKlines`):
· `NoFineKlines` — every candle is coarse (no 1-second data stored).
· `FineKlinesByCandle` — klines handed over already grouped (tests, small runs).
· the application's streamed source, reading the market data repository once.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
)


class FineKlines(ABC):
    """@brief The 1-second klines inside one candle, asked oldest candle first."""

    @abstractmethod
    def within(self, start: datetime, end: datetime) -> tuple[PriceBar, ...]:
        """The klines with `start <= time < end`, oldest first; empty when none
        are stored. Each call's `start` is at or after the previous `end`."""


class NoFineKlines(FineKlines):
    """No 1-second klines at all: every reactive candle is replayed coarse."""

    def within(self, start: datetime, end: datetime) -> tuple[PriceBar, ...]:
        return ()


class FineKlinesByCandle(FineKlines):
    """Klines already grouped by their candle's open time."""

    def __init__(self, by_candle: Mapping[datetime, tuple[PriceBar, ...]]) -> None:
        self._by_candle = MappingProxyType(dict(by_candle))

    def within(self, start: datetime, end: datetime) -> tuple[PriceBar, ...]:
        return tuple(k for k in self._by_candle.get(start, ()) if k.time < end)
