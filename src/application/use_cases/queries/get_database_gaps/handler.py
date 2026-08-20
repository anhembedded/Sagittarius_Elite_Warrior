from __future__ import annotations

import logging
from datetime import datetime

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.domain.models.data_gap import DataGap
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

from .query import (
    CoverageSegmentDTO,
    DataGapDTO,
    GetDatabaseGapsQuery,
    GetDatabaseGapsResult,
)

logger = logging.getLogger("App.QueryHandler")


class GetDatabaseGapsQueryHandler(
    IQueryHandler[GetDatabaseGapsQuery, GetDatabaseGapsResult]
):
    """
    @brief Handler for GetDatabaseGapsQuery.
    @details Scans SQLite klines, detects gaps, and generates timeline segments.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self.repository = repository

    def execute(self, query: GetDatabaseGapsQuery) -> GetDatabaseGapsResult:
        if not query.symbol:
            raise ValueError("Symbol cannot be empty")

        try:
            interval_vo = TimeFrame(query.interval)
        except ValueError as e:
            raise ValueError(f"Invalid interval: {query.interval}") from e

        status = self.repository.get_database_status(query.symbol, interval_vo)
        if (
            status.total_candles == 0
            or status.first_record is None
            or status.last_record is None
        ):
            return GetDatabaseGapsResult(
                symbol=query.symbol,
                interval=query.interval,
                gaps=[],
                total_missing_candles=0,
                total_gaps=0,
                coverage_percentage=0.0,
                coverage_segments=[],
            )

        gaps: list[DataGap] = self.repository.get_gaps(query.symbol, interval_vo)
        gap_dtos: list[DataGapDTO] = []
        total_missing = 0

        for idx, gap in enumerate(gaps, start=1):
            total_missing += gap.missing_candles
            duration_hrs = gap.duration_hours
            if duration_hrs < 1.0:
                duration_str = f"{int(duration_hrs * 60)}m"
            elif duration_hrs < 24.0:
                duration_str = f"{duration_hrs:.1f}h"
            else:
                duration_str = f"{duration_hrs / 24.0:.1f}d"

            gap_dtos.append(
                DataGapDTO(
                    gap_id=idx,
                    symbol=query.symbol,
                    interval=query.interval,
                    start_time=gap.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    end_time=gap.end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    fetch_start_time=gap.fetch_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    fetch_end_time=gap.fetch_end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    duration_text=duration_str,
                    missing_candles=gap.missing_candles,
                )
            )

        # Build timeline coverage segments
        segments = self._build_coverage_segments(
            first_record=status.first_record,
            last_record=status.last_record,
            gaps=gaps,
            interval=interval_vo,
        )

        total_expected = status.total_candles + total_missing
        coverage_pct = (
            round((status.total_candles / total_expected) * 100.0, 2)
            if total_expected > 0
            else 100.0
        )

        return GetDatabaseGapsResult(
            symbol=query.symbol,
            interval=query.interval,
            gaps=gap_dtos,
            total_missing_candles=total_missing,
            total_gaps=len(gaps),
            coverage_percentage=coverage_pct,
            coverage_segments=segments,
        )

    def _build_coverage_segments(
        self,
        first_record: datetime,
        last_record: datetime,
        gaps: list[DataGap],
        interval: TimeFrame,
    ) -> list[CoverageSegmentDTO]:
        total_seconds = max(1.0, (last_record - first_record).total_seconds())
        cadence_seconds = interval.to_seconds()

        if not gaps:
            total_candles = int(total_seconds // cadence_seconds) + 1
            return [
                CoverageSegmentDTO(
                    is_gap=False,
                    start_time=first_record.strftime("%Y-%m-%d %H:%M"),
                    end_time=last_record.strftime("%Y-%m-%d %H:%M"),
                    ratio=1.0,
                    candle_count=total_candles,
                )
            ]

        segments: list[CoverageSegmentDTO] = []
        current_cursor = first_record

        for gap in gaps:
            # Segment before gap (contiguous data)
            if gap.start_time > current_cursor:
                data_duration = (gap.start_time - current_cursor).total_seconds()
                ratio = max(0.01, min(1.0, data_duration / total_seconds))
                candle_count = max(1, int(data_duration // cadence_seconds))
                segments.append(
                    CoverageSegmentDTO(
                        is_gap=False,
                        start_time=current_cursor.strftime("%Y-%m-%d %H:%M"),
                        end_time=gap.start_time.strftime("%Y-%m-%d %H:%M"),
                        ratio=ratio,
                        candle_count=candle_count,
                    )
                )

            # Gap segment
            gap_duration = (gap.end_time - gap.start_time).total_seconds()
            gap_ratio = max(0.01, min(1.0, gap_duration / total_seconds))
            segments.append(
                CoverageSegmentDTO(
                    is_gap=True,
                    start_time=gap.start_time.strftime("%Y-%m-%d %H:%M"),
                    end_time=gap.end_time.strftime("%Y-%m-%d %H:%M"),
                    ratio=gap_ratio,
                    candle_count=gap.missing_candles,
                )
            )
            current_cursor = gap.end_time

        # Segment after the last gap if any
        if last_record > current_cursor:
            data_duration = (last_record - current_cursor).total_seconds()
            ratio = max(0.01, min(1.0, data_duration / total_seconds))
            candle_count = max(1, int(data_duration // cadence_seconds))
            segments.append(
                CoverageSegmentDTO(
                    is_gap=False,
                    start_time=current_cursor.strftime("%Y-%m-%d %H:%M"),
                    end_time=last_record.strftime("%Y-%m-%d %H:%M"),
                    ratio=ratio,
                    candle_count=candle_count,
                )
            )

        return segments
