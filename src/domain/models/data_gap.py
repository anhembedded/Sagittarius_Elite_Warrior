from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class DataGap:
    """
    @brief Domain Value Object representing a detected gap in historical market data.
    @details Defined by the boundary timestamps of contiguous klines and the missing candle count.
    """

    symbol: str
    interval: TimeFrame
    start_time: datetime  # Open time of the candle immediately before the gap
    end_time: datetime  # Open time of the candle immediately after the gap
    missing_candles: int

    @property
    def fetch_start_time(self) -> datetime:
        """Start time for exchange query (start_time + 1 cadence)."""
        cadence = timedelta(seconds=self.interval.to_seconds())
        return self.start_time + cadence

    @property
    def fetch_end_time(self) -> datetime:
        """End time for exchange query (end_time - 1 cadence)."""
        cadence = timedelta(seconds=self.interval.to_seconds())
        return self.end_time - cadence

    @property
    def duration_hours(self) -> float:
        """Duration of the missing gap in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600.0
