"""The Backtest mode's Drawdown and Monthly returns panels (`EPIC-033L`):
each built over the run's result and kept in step with it (`BOT-106D`).

They were two tabs of the Trades panel's own tab bar; as docks beside it,
the person tabs, splits or floats them, and the mode's perspective keeps
the arrangement.
"""

from __future__ import annotations

from typing import Any

from ._drawdown_chart_widget import DrawdownChartWidget
from ._monthly_returns_heatmap_widget import MonthlyReturnsHeatmapWidget
from .view_models.run_result_view_model import RunResultViewModel


def _points(run_result: RunResultViewModel) -> list[dict[str, float]]:
    return list(run_result.drawdownPoints)


def _years(run_result: RunResultViewModel) -> list[dict[str, Any]]:
    return list(run_result.yearlyReturns)


def drawdown_panel(run_result: RunResultViewModel) -> DrawdownChartWidget:
    """The drawdown chart of the run on screen."""
    panel = DrawdownChartWidget()
    panel.setObjectName("backtestDrawdown")
    panel.set_points(_points(run_result))
    run_result.drawdownPointsChanged.connect(
        lambda: panel.set_points(_points(run_result))
    )
    return panel


def monthly_returns_panel(
    run_result: RunResultViewModel,
) -> MonthlyReturnsHeatmapWidget:
    """The run's return per month, a row per year."""
    panel = MonthlyReturnsHeatmapWidget()
    panel.setObjectName("backtestMonthlyReturns")
    panel.set_rows(_years(run_result))
    run_result.yearlyReturnsChanged.connect(lambda: panel.set_rows(_years(run_result)))
    return panel
