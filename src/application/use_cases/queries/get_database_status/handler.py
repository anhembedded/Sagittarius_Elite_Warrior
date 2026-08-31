import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
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
            f"Handling GetDatabaseStatusQuery for {query.symbol} at {query.interval.value}"
        )

        if not query.symbol:
            raise ValueError("Invalid symbol")

        snapshot = self.repository.get_database_status(
            symbol=query.symbol, interval=query.interval
        )
        return DatabaseStatusDTO.from_snapshot(
            query.symbol, query.interval.value, snapshot
        )
