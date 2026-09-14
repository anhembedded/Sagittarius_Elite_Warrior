from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_backtest_range_coverage.coverage_builders import (
    build_backtest_range_coverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_backtest_range_coverage.query import (
    GetBacktestRangeCoverageQuery,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
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
