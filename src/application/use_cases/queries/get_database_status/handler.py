import logging
from Binace_Bot.src.application.ports.i_cqrs import IQueryHandler
from Binace_Bot.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Binace_Bot.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)

logger = logging.getLogger("App.QueryHandler")


class GetDatabaseStatusQueryHandler(
    IQueryHandler[GetDatabaseStatusQuery, DatabaseStatusDTO]
):
    """
    @brief Handler for GetDatabaseStatusQuery.
    @details Fetches the status of the local database for a specific symbol/interval.
    Returns a typed DatabaseStatusDTO — consistent with ScanAllDatabasesQueryHandler,
    no raw dict.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self.repository = repository

    def execute(self, query: GetDatabaseStatusQuery) -> DatabaseStatusDTO:
        logger.debug(
            f"Handling GetDatabaseStatusQuery for {query.symbol} at {query.interval}"
        )

        if not query.symbol:
            raise ValueError("Invalid symbol")

        try:
            interval_vo = TimeFrame(query.interval)
        except ValueError as e:
            logger.error(f"Invalid interval provided to query: {query.interval}")
            raise ValueError(f"Invalid interval: {query.interval}") from e

        snapshot = self.repository.get_database_status(
            symbol=query.symbol, interval=interval_vo
        )
        return DatabaseStatusDTO.from_snapshot(query.symbol, query.interval, snapshot)
