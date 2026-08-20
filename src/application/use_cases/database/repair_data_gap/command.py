from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class RepairDataGapResult:
    """
    @brief Result of a gap repair operation.
    """

    success: bool
    repaired_candles: int
    message: str


@dataclass(frozen=True)
class RepairDataGapCommand:
    """
    @brief Command to repair a specific data gap by fetching missing klines from Binance.
    """

    symbol: str
    interval: TimeFrame
    start_time: datetime
    end_time: datetime
    cancellation_requested: Callable[[], bool] | None = None
