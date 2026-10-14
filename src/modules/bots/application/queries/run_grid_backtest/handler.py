"""`EPIC-029D` — handler for `RunGridBacktestQuery`.

Reads what is stored and never fetches (`BUG-107`): the candles through
`IHistoricalKlines`, the 1-second klines through the repository's stream (the
source the historical-tick backtest reads), both of the bot's own venue's store
(`BUG-172`), then replays them with
`simulate_grid`. A venue that holds a position (`EPIC-039K`) is replayed by `FuturesReplay`
under the symbol's brackets and the funding settled in the period, which is the one thing
read from the exchange at run time (`futures_preparation.py`). A period with no stored candles is refused with
`missing_candles`, so the screen can offer a sync; a period too long for the
interval is refused before anything is loaded.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.futures_preparation import (
    brackets_of,
    funding_run_terms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.query import (
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.result import (
    GridBacktestAnswer,
    GridBacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.streamed_fine_klines import (
    StreamedFineKlines,
    price_bar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    plan_limits_of,
    plan_market_of,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_replay import (
    FuturesReplay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_run_terms import (
    FuturesRunTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestCancelled,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exposure_check import (
    exposure_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
    RangeExit,
    unset_parameters,
    unset_parameters_reason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.replay_engine import (
    EngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)

#: The most candles one replay draws: a month of 3-minute candles, a week of
#: 1-minute ones with room to spare. Beyond it the chart is unreadable and the
#: replay slow; a longer period wants a longer interval.
MAX_CANDLES = 20_000


#: The replay has no range exit (`EPIC-039H` stage 3 added the parameter; the Futures replay of
#: `EPIC-039K` has no event for it), so a definition that closes out of range is not replayed as
#: if it held: the result would show an outcome the bot will not produce.
_RANGE_EXIT_NOT_REPLAYED = (
    "This plan closes when the price leaves the range, which the backtest does not model yet; "
    "it would replay a bot that holds. Set it to hold to see the replay."
)


class RunGridBacktestQueryHandler(
    IQueryHandler[RunGridBacktestQuery, GridBacktestAnswer]
):
    def __init__(self, sources: IMarketDataSources) -> None:
        self._sources = sources

    def execute(self, query: RunGridBacktestQuery) -> GridBacktestAnswer:
        params = _params_of(query)
        if isinstance(params, GridBacktestRefusal):
            return params
        profile = venue_profile_of(query.venue)
        brackets: LeverageBrackets | None = None
        if profile is not None and profile.exposure_kind is ExposureKind.POSITION:
            found = brackets_of(query, params)
            if isinstance(found, GridBacktestRefusal):
                return found
            brackets = found
        # `BUG-172`: the candles stored from the market the bot's orders fill in.
        market_data = self._sources.ports_for(query.venue.market_data_venue)
        repository = market_data.repository
        market = plan_market_of(query.venue)
        count = repository.count_klines(
            market, query.symbol, query.interval, query.start, query.end
        )
        refused = _candles_refusal(query, count)
        if refused is not None:
            return refused
        engine: EngineFactory | None = None
        if brackets is not None:
            try:
                run = funding_run_terms(query, brackets, market_data.funding)
            except ExchangeRequestCancelledError:
                return GridBacktestCancelled(0, count)
            if isinstance(run, GridBacktestRefusal):
                return run
            engine = _futures_engine(params, query.terms, run)
        bars = tuple(
            price_bar(candle)
            for candle in market_data.history.load(
                market,
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
                market,
                query.symbol,
                TimeFrame.ONE_SECOND,
                start_time=query.start,
                end_time=query.end + length,
            )
        )
        inputs = GridBacktestInputs(
            params,
            query.terms,
            bars,
            length,
            fine,
            window=(query.start, query.end),
            engine=engine,
        )
        return simulate_grid(inputs, query.cancelled)


def _params_of(query: RunGridBacktestQuery) -> GridParams | GridBacktestRefusal:
    """The definition to replay, or why it cannot be replayed."""
    unset = unset_parameters(query.config)
    if unset:
        # `BOT-150`: a draft created with the minimum asks for what to
        # set, in the planner's words, not "lower is missing".
        return GridBacktestRefusal(unset_parameters_reason(unset))
    try:
        params = GridParams.from_config(query.config)
    except GridParamsError as exc:
        return GridBacktestRefusal(f"The parameters cannot be read: {exc}")
    # A backtest starts nothing, so it is judged against what the venue's market
    # allows, not against the markets a bot may run on in this build (`EPIC-039K`).
    refusal = exposure_refusal(params, plan_limits_of(query.venue))
    if refusal is not None:
        return GridBacktestRefusal(refusal.reason)
    if params.on_range_exit is RangeExit.CLOSE:
        return GridBacktestRefusal(_RANGE_EXIT_NOT_REPLAYED)
    return params


def _futures_engine(
    params: GridParams, terms: ExchangeTerms, run: FuturesRunTerms
) -> EngineFactory:
    """A position venue's ladder, replayed by `FuturesReplay` (`EPIC-039K`)."""
    return lambda first: FuturesReplay(params, terms, run, first)


def _candles_refusal(
    query: RunGridBacktestQuery, count: int
) -> GridBacktestRefusal | None:
    """Why `count` stored candles cannot be replayed, in words, or `None` when they can."""
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
    return None
