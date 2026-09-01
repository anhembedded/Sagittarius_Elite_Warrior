from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

logger = logging.getLogger("App.QueryHandler")

_DEFAULT_SCAN_INTERVALS = [
    TimeFrame.ONE_MINUTE.value,
    TimeFrame.FIVE_MINUTES.value,
    TimeFrame.FIFTEEN_MINUTES.value,
    TimeFrame.ONE_HOUR.value,
    TimeFrame.FOUR_HOURS.value,
    TimeFrame.ONE_DAY.value,
]


class ScanAllDatabasesQueryHandler(
    IQueryHandler[ScanAllDatabasesQuery, list[DatabaseStatusDTO]]
):
    """
    @brief Handler for ScanAllDatabasesQuery.
    @details Owns the nested iteration logic over all symbol/interval combinations.
    If symbols is not specified, auto-discovers all shards currently on disk.
    Entries with zero candles are skipped to avoid table clutter during bulk scans.
    Returns a typed list of DatabaseStatusDTO — no raw dicts.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, query: ScanAllDatabasesQuery) -> list[DatabaseStatusDTO]:
        """
        @brief Scans all requested symbols and returns formatted status DTOs.
        @param query ScanAllDatabasesQuery carrying lists of symbols and intervals.
        @return List of DatabaseStatusDTO, one per non-empty symbol/interval pair.
        """
        if query.cancellation_requested and query.cancellation_requested():
            logger.debug("[storage-vault] Database scan cancelled before it started.")
            return []

        symbols = (
            query.symbols if query.symbols else self._repository.list_available_shards()
        )
        raw_intervals = query.intervals if query.intervals else _DEFAULT_SCAN_INTERVALS
        intervals = self._parse_intervals(raw_intervals)

        logger.debug(
            f"Handling ScanAllDatabasesQuery for {len(symbols)} symbols "
            f"x {len(intervals)} intervals."
        )

        results: list[DatabaseStatusDTO] = []
        if not symbols or not intervals:
            return results

        # BUG-078: one task per symbol, not per (symbol, interval) pair — a shard
        # holds every interval of that symbol in one SQLite file, so scanning it
        # opens a single connection instead of `len(intervals)` of them.
        def _scan(symbol: str) -> list[DatabaseStatusDTO]:
            if query.cancellation_requested and query.cancellation_requested():
                return []
            return self._scan_symbol(symbol, intervals)

        max_workers = min(len(symbols), 10)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for dtos in executor.map(_scan, symbols):
                results.extend(dtos)

        if query.cancellation_requested and query.cancellation_requested():
            logger.debug(
                "[storage-vault] Database scan observed cancellation and skipped queued pairs."
            )

        return results

    @staticmethod
    def _parse_intervals(raw_intervals: list[str]) -> list[TimeFrame]:
        parsed: list[TimeFrame] = []
        for interval in raw_intervals:
            try:
                parsed.append(TimeFrame(interval))
            except ValueError:
                logger.warning(f"Skipping invalid interval: {interval!r}")
        return parsed

    def _scan_symbol(
        self, symbol: str, intervals: list[TimeFrame]
    ) -> list[DatabaseStatusDTO]:
        """
        @brief Fetches and formats status for every requested interval of one symbol.
        @return DTOs for the non-empty intervals only (empty ones are skipped to
        prevent table clutter during a "Scan All" operation).
        """
        try:
            snapshots = self._repository.get_database_status_for_intervals(
                symbol, intervals
            )
        except Exception as exc:  # noqa: BLE001 - boundary: report per-symbol scan failure without aborting the batch
            logger.error(f"Error scanning {symbol}: {exc}")
            return []

        return [
            DatabaseStatusDTO.from_snapshot(symbol, interval_value, snapshot)
            for interval_value, snapshot in snapshots.items()
            if snapshot.total_candles > 0
        ]
