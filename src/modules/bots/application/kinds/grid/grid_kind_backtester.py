"""`EPIC-040B` — the Grid's backtest behind the kind-neutral port.

Runs the existing `RunGridBacktestQuery` handler and maps its answer into the kind-neutral
outcome: the replay's numbers are the handler's, untouched (`EPIC-039B`'s oracle and `EPIC-039K`'s
tests pin them); only their shape changes. The Grid's own result stays whole as the outcome's
`detail`, which the Grid's chart overlay reads. The Grid replays from its first candle, so
`request.warmup` is ignored.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestAnswer,
    GridBacktestRefusal,
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    IKindBacktester,
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
    BacktestCancelled,
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestBar,
    BacktestFill,
    BacktestOutcome,
    BacktestProvenance,
    DataWindow,
    EquityPoint,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid import (
    grid_backtest_result as grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_figures import (
    grid_figures,
    grid_notes,
)


class GridKindBacktester(IKindBacktester):
    """@brief The Grid's replay, answered in the kind-neutral shape."""

    def __init__(
        self, handler: IQueryHandler[RunGridBacktestQuery, GridBacktestAnswer]
    ) -> None:
        self._handler = handler

    def run(self, request: KindBacktestRequest) -> BacktestAnswer:
        answer = self._handler.execute(
            RunGridBacktestQuery(
                request.symbol,
                request.config,
                request.terms,
                request.interval,
                request.start,
                request.end,
                request.venue,
                cancelled=request.cancelled,
                brackets=request.brackets,
                funding=request.funding,
            )
        )
        if isinstance(answer, grid.GridBacktestResult):
            return outcome_of(answer)
        if isinstance(answer, GridBacktestRefusal):
            return BacktestRefusal(
                answer.reason, answer.missing_candles, answer.funding_unavailable
            )
        return BacktestCancelled(answer.replayed_bars, answer.total_bars)


def outcome_of(result: grid.GridBacktestResult) -> BacktestOutcome:
    """@brief A Grid replay in the kind-neutral shape; every field of the result lands in the
    outcome (the curves, the fills, the fees, the provenance) or in its `detail`."""
    return BacktestOutcome(
        provenance=_provenance_of(result.provenance),
        bars=tuple(
            BacktestBar(bar.time, bar.open, bar.high, bar.low, bar.close)
            for bar in result.bars
        ),
        equity=tuple(
            EquityPoint(point.time, point.grid, point.buy_and_hold)
            for point in result.equity
        ),
        fills=tuple(
            BacktestFill(
                fill.time,
                fill.side,
                fill.price,
                fill.quantity,
                fill.fee_quote,
                fill.label,
                fill.maker,
            )
            for fill in result.fills
        ),
        maker_fees=result.maker_fees,
        taker_fees=result.taker_fees,
        figures=grid_figures(result),
        notes=grid_notes(result),
        detail=result,
    )


def _provenance_of(provenance: grid.BacktestProvenance) -> BacktestProvenance:
    window = provenance.window
    return BacktestProvenance(
        provenance.config,
        provenance.maker_fee,
        provenance.taker_fee,
        provenance.first_candle,
        provenance.last_candle,
        provenance.fill_rule,
        None
        if window is None
        else DataWindow(
            window.start, window.end, window.expected_candles, window.stored_candles
        ),
    )
