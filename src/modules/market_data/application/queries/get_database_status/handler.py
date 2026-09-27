import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)

logger = logging.getLogger("App.QueryHandler")

#: `EPIC-027A` — see `scan_all_databases/handler.py`'s identical constant for
#: why this is Spot and not yet a caller-chosen market.
_MARKET = MarketType.SPOT


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
            market=_MARKET, symbol=query.symbol, interval=query.interval
        )
        return DatabaseStatusDTO.from_snapshot(
            query.symbol, query.interval.value, snapshot
        )
