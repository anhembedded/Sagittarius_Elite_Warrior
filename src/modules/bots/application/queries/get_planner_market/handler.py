"""`EPIC-029F` — handler for `GetPlannerMarketQuery`.

The symbol's filters and fees and the current price come from the venue
(`IOrderEntryTerms`), as the start check reads them (`grid_start_preconditions`),
so the panel judges a plan against the numbers the start will use. The daily
ATR and the Bollinger band come from the stored daily candles: the planner
reads what is stored and never fetches.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.daily_atr_reader import (
    DailyAtrReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.planner_numbers import (
    read_planner_numbers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market.query import (
    GetPlannerMarketQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market.result import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.bands import (
    BOLLINGER_DEFAULT_PERIOD,
    bollinger,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.volatility import (
    ATR_DEFAULT_PERIOD,
    HighLowClose,
    atr_range,
)


class GetPlannerMarketQueryHandler(IQueryHandler[GetPlannerMarketQuery, PlannerMarket]):
    def __init__(
        self,
        ports: IVenueTradingPorts,
        caps: OwnerBudgetCaps,
        sources: IMarketDataSources,
        clock: IBotClock,
    ) -> None:
        self._ports = ports
        self._caps = caps
        self._atr = DailyAtrReader(lambda: sources)
        self._clock = clock

    def execute(self, query: GetPlannerMarketQuery) -> PlannerMarket:
        numbers = read_planner_numbers(
            self._ports, self._caps, query.venue, query.symbol
        )
        if isinstance(numbers, str):
            return _unreadable(numbers)
        terms, view = numbers
        reading = self._atr.read(query.venue, query.symbol, self._clock.now())
        hlc = reading.candles
        return PlannerMarket(
            terms=terms,
            market=replace(view, daily_atr=reading.value),
            atr_range=_atr_suggestion(hlc),
            bollinger=_bollinger_suggestion(hlc),
        )


def _unreadable(problem: str) -> PlannerMarket:
    return PlannerMarket(None, None, None, None, problem)


def _atr_suggestion(hlc: tuple[HighLowClose, ...]) -> SuggestedRange | None:
    if len(hlc) <= ATR_DEFAULT_PERIOD:
        return None
    suggested = atr_range(hlc)
    return SuggestedRange(suggested.lower, suggested.upper)


def _bollinger_suggestion(hlc: tuple[HighLowClose, ...]) -> SuggestedRange | None:
    if len(hlc) < BOLLINGER_DEFAULT_PERIOD:
        return None
    bands = bollinger(tuple(candle.close for candle in hlc))
    return SuggestedRange(bands.lower, bands.upper)
