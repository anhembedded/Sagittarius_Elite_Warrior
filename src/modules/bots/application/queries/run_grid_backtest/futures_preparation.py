"""`EPIC-039K` — what a Futures backtest reads before it replays: brackets and funding.

@details Everything here is refused in words rather than guessed: a symbol without brackets
has no liquidation price, a leverage above its bracket would be rejected by the exchange, and
a period whose funding could not be read is either refused or replayed *saying so*
(`FundingRequirement`, decision O9). The funding history is read from the **market-data
venue** the candles come from (`BUG-172`), at the moment the user ran the backtest and never
stored (`IFundingHistory`'s docstring gives the reason).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.futures_backtest_terms import (
    futures_run_terms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.query import (
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.result import (
    GridBacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    plan_market_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    FundingSchedule,
    FundingSettlement,
    no_funding,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_run_terms import (
    FuturesRunTerms,
    bracket_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingEvent,
    FundingHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_funding_history import (
    IFundingHistory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)

logger = logging.getLogger("App.RunGridBacktest")


def brackets_of(
    query: RunGridBacktestQuery, params: GridParams
) -> LeverageBrackets | GridBacktestRefusal:
    """The symbol's brackets, when the query has them and they allow `params`' leverage."""
    brackets = query.brackets
    if brackets is None:
        return GridBacktestRefusal(
            f"The leverage brackets of {query.symbol} were not read, so its "
            "liquidation price cannot be worked out; read them and run again."
        )
    refusal = bracket_refusal(params, brackets)
    return brackets if refusal is None else GridBacktestRefusal(refusal)


def funding_run_terms(
    query: RunGridBacktestQuery,
    brackets: LeverageBrackets,
    history: IFundingHistory,
) -> FuturesRunTerms | GridBacktestRefusal:
    """The terms of the replay, the funding history read for the query's period.

    @raise ExchangeRequestCancelledError the query was cancelled while the history was read.
    """
    try:
        events = history.funding_between(
            plan_market_of(query.venue),
            query.symbol,
            query.start,
            query.end,
            query.cancelled,
        )
    except FundingHistoryUnavailableError as exc:
        return _without_history(query, brackets, exc.reason)
    schedule = _schedule_of(events)
    logger.info(
        "[futures-backtest] %s %s..%s: funding %s",
        query.symbol,
        query.start.isoformat(),
        query.end.isoformat(),
        schedule.note,
    )
    return futures_run_terms(query.terms, brackets, schedule)


def _without_history(
    query: RunGridBacktestQuery, brackets: LeverageBrackets, reason: str
) -> FuturesRunTerms | GridBacktestRefusal:
    if query.funding is FundingRequirement.REQUIRED:
        return GridBacktestRefusal(
            f"{reason} A Futures backtest without funding flatters a leveraged "
            "grid, so none was run.",
            funding_unavailable=True,
        )
    note = f"FUNDING IS NOT INCLUDED in this result: {reason}"
    logger.info("[futures-backtest] %s: %s", query.symbol, note)
    return futures_run_terms(query.terms, brackets, no_funding(note))


def _schedule_of(events: tuple[FundingEvent, ...]) -> FundingSchedule:
    settlements = tuple(
        FundingSettlement(event.time, event.rate, event.mark_price) for event in events
    )
    unpriced = sum(1 for event in events if event.mark_price is None)
    note = (
        f"{len(settlements)} funding settlements recorded by the exchange in the period"
    )
    if unpriced:
        note += (
            f"; {unpriced} carry no mark price (older than 2023-11-01) and are "
            "charged at the candle's price"
        )
    return FundingSchedule(settlements, True, note + ".")
