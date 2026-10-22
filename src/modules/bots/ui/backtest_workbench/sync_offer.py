"""`BOT-233` — what the next Sync candles fetches, and what follows it.

Two things offer a sync: a run that found candles missing (it runs again once they are stored) and the
stored candles under the chart (they are read again). A run's offer is the older, so it wins while it
stands.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_window import (
    CandleWindow,
    window_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.outcome_view import (
    missing_candles,
)


@dataclass(frozen=True, slots=True)
class SyncPlan:
    window: CandleWindow
    #: The run that offered the sync runs again after it.
    then_run: bool


def sync_plan(
    last: RunBacktestQuery | None,
    refusal: BacktestRefusal | None,
    outcome: BacktestOutcome | None,
    drawn: CandleWindow | None,
) -> SyncPlan | None:
    """The sync on offer, or `None` when nothing offers one."""
    if last is not None and (
        (refusal is not None and refusal.missing_candles) or missing_candles(outcome)
    ):
        return SyncPlan(window_of(last.request), then_run=True)
    return SyncPlan(drawn, then_run=False) if drawn is not None else None
