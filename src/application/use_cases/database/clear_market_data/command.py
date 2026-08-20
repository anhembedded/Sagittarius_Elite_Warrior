from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class ClearMarketDataCommand:
    """
    @brief Command to delete klines for a specific symbol/interval or purge the whole vault.
    """

    symbol: str = ""
    interval: TimeFrame | None = None
    purge_all: bool = False


@dataclass(frozen=True)
class ClearMarketDataResult:
    """
    @brief Typed outcome of executing a ClearMarketDataCommand.
    """

    deleted_records: int
    success: bool
    message: str
