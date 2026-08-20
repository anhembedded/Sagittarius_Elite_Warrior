from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DataGapDTO:
    """
    @brief Data Transfer Object for a single gap in historical market data.
    """

    gap_id: int
    symbol: str
    interval: str
    start_time: str
    end_time: str
    fetch_start_time: str
    fetch_end_time: str
    duration_text: str
    missing_candles: int


@dataclass(frozen=True)
class CoverageSegmentDTO:
    """
    @brief DTO representing a continuous block or gap segment on the timeline bar.
    """

    is_gap: bool
    start_time: str
    end_time: str
    ratio: float  # Proportional width on timeline (0.0 to 1.0)
    candle_count: int


@dataclass(frozen=True)
class GetDatabaseGapsResult:
    """
    @brief Complete inspection result containing detected gaps and coverage breakdown.
    """

    symbol: str
    interval: str
    gaps: list[DataGapDTO] = field(default_factory=list)
    total_missing_candles: int = 0
    total_gaps: int = 0
    coverage_percentage: float = 100.0
    coverage_segments: list[CoverageSegmentDTO] = field(default_factory=list)


@dataclass(frozen=True)
class GetDatabaseGapsQuery:
    """
    @brief Query to inspect all gaps in market data for a given symbol and interval.
    """

    symbol: str
    interval: str
