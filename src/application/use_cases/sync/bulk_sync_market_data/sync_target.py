"""`EPIC-018D` — a named (symbol, interval) pair, replacing the raw
positional 2-tuple `BulkSyncMarketDataCommand.targets` used to carry."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class SyncTarget:
    """One symbol/interval pair `BulkSyncMarketDataCommand` should sync."""

    symbol: str
    interval: TimeFrame
