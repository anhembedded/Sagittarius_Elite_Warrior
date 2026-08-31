from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    BacktestRangeCoverage,
    build_backtest_range_coverage,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_backtest_range_coverage.query import (
    GetBacktestRangeCoverageQuery,
)


class GetBacktestRangeCoverageQueryHandler(
    IQueryHandler[GetBacktestRangeCoverageQuery, BacktestRangeCoverage]
):
    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, query: GetBacktestRangeCoverageQuery) -> BacktestRangeCoverage:
        interval = query.interval
        snapshot = self._repository.get_range_coverage(
            query.symbol,
            interval,
            query.start_time,
            query.end_time,
            query.now,
        )
        return build_backtest_range_coverage(
            snapshot,
            interval,
            start_time=query.start_time,
            end_time=query.end_time,
            now=query.now,
        )
