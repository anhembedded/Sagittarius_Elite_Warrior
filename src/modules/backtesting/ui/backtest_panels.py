"""The Backtest mode's panels (`EPIC-033L`), built over the view model and
docked where HLD §11.2.1 lists them:

| Panel | Dock area |
| :--- | :--- |
| Run setup (`RunSetupPanel`) | left (`Place.NAVIGATOR`) |
| Metrics (`BackTestTopPanel`: banners and figures) | right (`Place.RAIL`) |
| Trades, Drawdown, Monthly returns, Monte Carlo | bottom, tabbed, Trades in front |

A panel added later is one field and one row here; the view takes the set
whole.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDockWidget, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)

from ._drawdown_chart_widget import DrawdownChartWidget
from ._monthly_returns_heatmap_widget import MonthlyReturnsHeatmapWidget
from .backtest_top_panel import BackTestTopPanel
from .backtest_trade_logs_panel import BackTestTradeLogsPanel
from .monte_carlo_panel import MonteCarloPanel
from .result_panels import drawdown_panel, monthly_returns_panel
from .run_setup_panel import RunSetupPanel

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

RUN_SETUP_DOCK = "Run setup"
METRICS_DOCK = "Metrics"
TRADES_DOCK = "Trades"
DRAWDOWN_DOCK = "Drawdown"
MONTHLY_RETURNS_DOCK = "Monthly returns"
MONTE_CARLO_DOCK = "Monte Carlo"


@dataclass(frozen=True)
class BacktestPanels:
    """Every panel of the mode, each the content of one dock."""

    run_setup: RunSetupPanel
    metrics: BackTestTopPanel
    trades: BackTestTradeLogsPanel
    drawdown: DrawdownChartWidget
    monthly_returns: MonthlyReturnsHeatmapWidget
    monte_carlo: MonteCarloPanel

    def docked(self) -> tuple[tuple[Place, QWidget, str], ...]:
        """Where each goes, in the order the docks are made."""
        return (
            (Place.NAVIGATOR, self.run_setup, RUN_SETUP_DOCK),
            (Place.RAIL, self.metrics, METRICS_DOCK),
            (Place.CONSOLE, self.trades, TRADES_DOCK),
            (Place.CONSOLE, self.drawdown, DRAWDOWN_DOCK),
            (Place.CONSOLE, self.monthly_returns, MONTHLY_RETURNS_DOCK),
            (Place.CONSOLE, self.monte_carlo, MONTE_CARLO_DOCK),
        )


def build_panels(view_model: BackTestViewModel) -> BacktestPanels:
    return BacktestPanels(
        run_setup=RunSetupPanel(view_model),
        metrics=BackTestTopPanel(view_model),
        trades=BackTestTradeLogsPanel(view_model),
        drawdown=drawdown_panel(view_model.run_result),
        monthly_returns=monthly_returns_panel(view_model.run_result),
        monte_carlo=MonteCarloPanel(view_model),
    )


def place_panels(surface: WorkbenchSurface, panels: BacktestPanels) -> None:
    for place, widget, title in panels.docked():
        surface.place_widget(place, widget, title=title)
    # The bottom docks are tabbed; the trades are what a run is read by.
    dock_of(surface, panels.trades).raise_()


def dock_of(surface: WorkbenchSurface, widget: QWidget) -> QDockWidget:
    """The dock `widget` is the content of."""
    for dock in surface.findChildren(QDockWidget):
        if dock.widget() is widget:
            return dock
    raise LookupError(f"the surface placed no dock for {widget.objectName()!r}")
