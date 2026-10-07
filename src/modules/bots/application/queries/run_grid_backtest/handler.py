"""`EPIC-029D` — handler for `RunGridBacktestQuery`.

Reads what is stored and never fetches (`BUG-107`): the candles through
`IHistoricalKlines`, the 1-second klines through the repository's stream (the
source the historical-tick backtest reads), both of the bot's own venue's store
(`BUG-172`), then replays them with
`simulate_grid`. A period with no stored candles is refused with
`missing_candles`, so the screen can offer a sync; a period too long for the
interval is refused before anything is loaded.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.query import (
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.result import (
    GridBacktestAnswer,
    GridBacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.streamed_fine_klines import (
    StreamedFineKlines,
    price_bar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
    unset_parameters,
    unset_parameters_reason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)

#: The most candles one replay draws: a month of 3-minute candles, a week of
#: 1-minute ones with room to spare. Beyond it the chart is unreadable and the
#: replay slow; a longer period wants a longer interval.
MAX_CANDLES = 20_000


class RunGridBacktestQueryHandler(
    IQueryHandler[RunGridBacktestQuery, GridBacktestAnswer]
):
    def __init__(self, sources: IMarketDataSources) -> None:
        self._sources = sources

    def execute(self, query: RunGridBacktestQuery) -> GridBacktestAnswer:
        unset = unset_parameters(query.config)
        if unset:
            # `BOT-150`: a draft created with the minimum asks for what to
            # set, in the planner's words, not "lower is missing".
            return GridBacktestRefusal(unset_parameters_reason(unset))
        try:
            params = GridParams.from_config(query.config)
        except GridParamsError as exc:
            return GridBacktestRefusal(f"The parameters cannot be read: {exc}")
        # `BUG-172`: the candles stored from the market the bot's orders fill in.
        market_data = self._sources.ports_for(query.venue.market_data_venue)
        repository = market_data.repository
        count = repository.count_klines(
            MarketType.SPOT, query.symbol, query.interval, query.start, query.end
        )
        if count == 0:
            return GridBacktestRefusal(
                f"No {query.interval.value} candles of {query.symbol} are stored "
                f"between {query.start:%Y-%m-%d %H:%M} and {query.end:%Y-%m-%d %H:%M}.",
                missing_candles=True,
            )
        if count > MAX_CANDLES:
            return GridBacktestRefusal(
                f"{count} {query.interval.value} candles is more than one backtest "
                f"draws ({MAX_CANDLES}); choose a shorter period or a longer interval."
            )
        bars = tuple(
            price_bar(candle)
            for candle in market_data.history.load(
                MarketType.SPOT,
                query.symbol,
                query.interval,
                limit=count,
                start_time=query.start,
                end_time=query.end,
            )
        )
        length = timedelta(seconds=query.interval.to_seconds())
        fine = StreamedFineKlines(
            repository.stream_klines(
                MarketType.SPOT,
                query.symbol,
                TimeFrame.ONE_SECOND,
                start_time=query.start,
                end_time=query.end + length,
            )
        )
        inputs = GridBacktestInputs(
            params, query.terms, bars, length, fine, window=(query.start, query.end)
        )
        return simulate_grid(inputs, query.cancelled)
