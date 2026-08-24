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
        @brief Scans all symbol/interval pairs and returns formatted status DTOs.
        @param query ScanAllDatabasesQuery carrying lists of symbols and intervals.
        @return List of DatabaseStatusDTO, one per non-empty symbol/interval pair.
        """
        if query.cancellation_requested and query.cancellation_requested():
            logger.debug("[storage-vault] Database scan cancelled before it started.")
            return []

        symbols = (
            query.symbols if query.symbols else self._repository.list_available_shards()
        )
        intervals = query.intervals if query.intervals else _DEFAULT_SCAN_INTERVALS

        logger.debug(
            f"Handling ScanAllDatabasesQuery for {len(symbols)} symbols "
            f"x {len(intervals)} intervals."
        )

        results: list[DatabaseStatusDTO] = []
        tasks = [(symbol, interval) for symbol in symbols for interval in intervals]

        if not tasks:
            return results

        def _scan(args: tuple[str, str]) -> DatabaseStatusDTO | None:
            if query.cancellation_requested and query.cancellation_requested():
                return None
            return self._scan_single(*args)

        max_workers = min(len(tasks), 10)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for dto in executor.map(_scan, tasks):
                if dto is not None:
                    results.append(dto)

        if query.cancellation_requested and query.cancellation_requested():
            logger.debug(
                "[storage-vault] Database scan observed cancellation and skipped queued pairs."
            )

        return results

    def _scan_single(self, symbol: str, interval: str) -> DatabaseStatusDTO | None:
        """
        @brief Fetches and formats the status for a single symbol/interval pair.
        @return A DatabaseStatusDTO, or None if the database is empty (total_candles == 0).
        """
        try:
            interval_vo = TimeFrame(interval)
        except ValueError:
            logger.warning(f"Skipping invalid interval: {interval!r}")
            return None

        try:
            snapshot = self._repository.get_database_status(
                symbol=symbol, interval=interval_vo
            )
        except Exception as exc:  # noqa: BLE001 - boundary: report per-symbol scan failure without aborting the batch
            logger.error(f"Error scanning {symbol} ({interval}): {exc}")
            return None

        # Skip empty databases to prevent clutter during a "Scan All" operation.
        if snapshot.total_candles == 0:
            return None

        return DatabaseStatusDTO.from_snapshot(symbol, interval, snapshot)
