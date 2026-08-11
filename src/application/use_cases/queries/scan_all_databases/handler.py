import logging

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


class ScanAllDatabasesQueryHandler(
    IQueryHandler[ScanAllDatabasesQuery, list[DatabaseStatusDTO]]
):
    """
    @brief Handler for ScanAllDatabasesQuery.
    @details Owns the nested iteration logic over all symbol/interval combinations,
    removing this orchestration responsibility from the Presenter (Domain Leakage fix).
    Entries with zero candles are skipped to avoid table clutter during bulk scans.
    Returns a typed list of DatabaseStatusDTO — no raw dicts.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, query: ScanAllDatabasesQuery) -> list[DatabaseStatusDTO]:
        """
        @brief Scans all symbol/interval pairs and returns formatted status DTOs.
        @param query ScanAllDatabasesQuery carrying the lists of symbols and intervals.
        @return List of DatabaseStatusDTO, one per non-empty symbol/interval pair.
        """
        logger.debug(
            f"Handling ScanAllDatabasesQuery for {len(query.symbols)} symbols "
            f"x {len(query.intervals)} intervals."
        )

        results: list[DatabaseStatusDTO] = []

        for symbol in query.symbols:
            for interval in query.intervals:
                dto = self._scan_single(symbol, interval)
                if dto is not None:
                    results.append(dto)

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
