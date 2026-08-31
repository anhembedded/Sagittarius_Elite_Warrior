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
_TRACE_PREFIX = "BACKTEST_TRACE"


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

    def _log_trace(self, action: str, **fields: object) -> None:
        suffix = " ".join(f"{key}={value!r}" for key, value in fields.items())
        logger.info(f"{_TRACE_PREFIX} action={action} {suffix}".rstrip())

    def execute(
        self, query: GetHistoricalKlinesQuery
    ) -> list[MarketData] | dict[str, list[MarketData]]:
        self._log_trace(
            "query_execute_start",
            symbol=query.symbol,
            timeframe=query.interval.value,
            limit=query.limit,
            start=query.start_time,
            end=query.end_time,
            order_by_desc=query.order_by_desc,
        )
        logger.debug(
            f"Handling GetHistoricalKlinesQuery for {query.symbol} at {query.interval.value} (limit={query.limit})"
        )

        if isinstance(query.symbol, list):
            return self._execute_multi(query, query.interval)

        return self._execute_single(query, query.interval)

    def _execute_multi(
        self, query: GetHistoricalKlinesQuery, interval_vo: TimeFrame
    ) -> dict[str, list[MarketData]]:
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
        self._log_trace(
            "query_execute_complete_multi",
            symbols=len(results),
            rows={sym: len(klines) for sym, klines in results.items()},
        )
        return results

    def _execute_single(
        self, query: GetHistoricalKlinesQuery, interval_vo: TimeFrame
    ) -> list[MarketData]:
        result = self.repository.get_klines(
            symbol=query.symbol,
            interval=interval_vo,
            start_time=query.start_time,
            end_time=query.end_time,
            limit=query.limit,
            order_by_desc=query.order_by_desc,
        )
        self._log_trace(
            "query_execute_complete",
            symbol=query.symbol,
            rows=len(result),
        )
        return result
