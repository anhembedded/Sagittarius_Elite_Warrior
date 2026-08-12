import logging
from concurrent.futures import ThreadPoolExecutor

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

logger = logging.getLogger("App.QueryHandler")


class GetHistoricalKlinesQueryHandler(
    IQueryHandler[
        GetHistoricalKlinesQuery, list[MarketData] | dict[str, list[MarketData]]
    ]
):
    """
    @brief Handler for GetHistoricalKlinesQuery.
    @details Fetches static market data from the repository (Database).
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self.repository = repository

    def execute(
        self, query: GetHistoricalKlinesQuery
    ) -> list[MarketData] | dict[str, list[MarketData]]:
        logger.debug(
            f"Handling GetHistoricalKlinesQuery for {query.symbol} at {query.interval} (limit={query.limit})"
        )

        try:
            interval_vo = TimeFrame(query.interval)
        except ValueError as e:
            logger.error(f"Invalid interval provided to query: {query.interval}")
            raise ValueError(f"Invalid interval: {query.interval}") from e

        if isinstance(query.symbol, list):
            results = {}

            def fetch_symbol(sym: str) -> tuple[str, list[MarketData]]:
                return sym, self.repository.get_klines(
                    symbol=sym,
                    interval=interval_vo,
                    start_time=query.start_time,
                    end_time=query.end_time,
                    limit=query.limit,
                    order_by_desc=query.order_by_desc,
                )

            max_workers = min(len(query.symbol), 10) if query.symbol else 1
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for sym, klines in executor.map(fetch_symbol, query.symbol):
                    results[sym] = klines
            return results

        return self.repository.get_klines(
            symbol=query.symbol,
            interval=interval_vo,
            start_time=query.start_time,
            end_time=query.end_time,
            limit=query.limit,
            order_by_desc=query.order_by_desc,
        )
