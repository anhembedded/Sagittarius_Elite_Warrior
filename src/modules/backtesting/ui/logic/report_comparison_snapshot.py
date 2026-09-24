"""`ReportComparisonSnapshot` — the boundary type between `BackTestPresenter`
and `BOT-115D`'s "compare 2 reports" dialog.

@details Same reasoning as `ExtendedMetricsSnapshot` (its own module
docstring): a cross-boundary contract is a named type, not two loose values
passed around by convention (`architecture-rule.md` §2.1). `BacktestResult`
already carries its own computed `BacktestMetrics` and `equity_curve`
(`backtest_result.py`), so this type adds nothing beyond pairing a result
with the `BacktestRunConfig` that produced it — the one piece `BacktestResult`
itself does not know.

Frozen and plain data — no behaviour belongs here, same as
`ExtendedMetricsSnapshot`."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)


@dataclass(frozen=True)
class ReportComparisonSnapshot:
    """One side of a report comparison — the config that produced a run,
    paired with its result. `BackTestViewModel.run_result` retains one of
    these for "the result currently on screen" (`None` before the first
    successful run); the comparison dialog builds a second one itself from
    a loaded `.sagi-report.json` file."""

    run_config: BacktestRunConfig
    result: BacktestResult
