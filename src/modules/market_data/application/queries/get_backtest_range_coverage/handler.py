"""Computing range coverage: the implementation behind `IRangeCoverage`.

**Why this file no longer handles a query.** Until `EPIC-025` PR 1.2 it was
`GetBacktestRangeCoverageQueryHandler`, an `IQueryHandler` two backtest
coordinators dispatched. PR 1.2 published `IRangeCoverage` and moved both
onto it, which left the query class, its `execute()` and its dispatcher
binding with no caller anywhere in `src/` — the same retirement PR 1.1a's
cleanup made for `GetHistoricalKlinesQuery`, for the same measured reason:
a registration kept alive for a hypothetical consumer is the accidental
complexity this epic exists to remove.

The arithmetic itself never lived here — `coverage_builders.py` owns it, with
its own tests — and still does not. This class reads the repository and hands
the snapshot to the builder.
"""

from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_backtest_range_coverage.coverage_builders import (
    build_backtest_range_coverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)


class RangeCoverageService(IRangeCoverage):
    """How much of a requested range is stored, with the diagnosis."""

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def coverage(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> BacktestRangeCoverage:
        # `EPIC-027A` added `market` to `IMarketDataRepository`; `IRangeCoverage`
        # itself stays market-less until `EPIC-027D` gives the backtest screen a
        # market to choose. Pinned to Spot, what this path has always read.
        snapshot = self._repository.get_range_coverage(
            MarketType.SPOT,
            symbol,
            interval,
            start_time,
            end_time,
            now,
        )
        return build_backtest_range_coverage(
            snapshot,
            interval,
            start_time=start_time,
            end_time=end_time,
            now=now,
        )
