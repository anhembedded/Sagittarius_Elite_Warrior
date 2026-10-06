"""`BOT-107B` — the Monte Carlo trade-reshuffling simulation, as the Backtest
mode's bottom panel beside Trades (`EPIC-033L`, HLD §11.2.1). Tools → Monte
Carlo brings it to the front; it was a modal overlay, which hid the run it
simulates.

Sourced from the same retained `BackTestViewModel.run_result
.comparison_snapshot()` `OutOfSampleComparisonDialog` reads (`result.trades`,
`result.initial_balance`) — no new "which run is this for" state needed.
Running the simulation itself is the Presenter's job
(`MonteCarloCoordinator`, off the Qt thread): this panel only asks for it
(`requestRunMonteCarlo`) and renders whatever `run_result
.monte_carlo_result()`/`.monte_carlo_error()` comes back, on its own
`monteCarloResultChanged` signal — a Monte Carlo run completes on its
own schedule (a button click, not a backtest finishing), so it does not
share `statCardsChanged`. The panel stays open while runs come and go, so
it also follows `comparisonSnapshotChanged` to judge what it can simulate.

Kept apart from `logic/monte_carlo_rules.py` (the pure formatting/bucketing
math) per `architecture-rule.md` §5, same split every other modal here uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.monte_carlo_rules import (
    build_drawdown_histogram_buckets,
    build_spaghetti_chart_series,
    build_summary_readout,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import ReadoutSlot

from ._monte_carlo_drawdown_histogram_widget import (
    MonteCarloDrawdownHistogramWidget,
)
from ._monte_carlo_spaghetti_chart_widget import MonteCarloSpaghettiChartWidget

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

_MIN_ITERATIONS = 1000
_MAX_ITERATIONS = 10000
_ITERATIONS_STEP = 1000
_DEFAULT_ITERATIONS = 5000
_MIN_TRADES_REQUIRED = 2
_NO_RUN_TEXT = "Run a backtest first to simulate its trades."
_NOT_ENOUGH_TRADES_TEXT = (
    "This run has too few trades to reshuffle — Monte Carlo needs at least "
    f"{_MIN_TRADES_REQUIRED}."
)
_READY_TEXT = "Choose an iteration count and run the simulation."


class MonteCarloPanel(QWidget):  # base-exempt: a dock's content, not a surface
    """@brief Trade-reshuffling risk distribution — summary stats, the
    simulated-equity spaghetti chart, and the max-drawdown histogram."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setObjectName("monteCarloPanel")
        self.body_layout = QVBoxLayout(self)

        self._build_controls_row()
        self._build_description_label()
        self._build_summary()
        self._build_charts()

        view_model.run_result.monteCarloResultChanged.connect(self.refresh)
        view_model.run_result.comparisonSnapshotChanged.connect(self.refresh)
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_controls_row(self) -> None:
        row = QHBoxLayout()
        simulations = QLabel("Simu&lations:")
        row.addWidget(simulations)

        self._spin_iterations = QSpinBox()
        self._spin_iterations.setObjectName("spnMonteCarloIterations")
        self._spin_iterations.setRange(_MIN_ITERATIONS, _MAX_ITERATIONS)
        self._spin_iterations.setSingleStep(_ITERATIONS_STEP)
        self._spin_iterations.setValue(_DEFAULT_ITERATIONS)
        simulations.setBuddy(self._spin_iterations)
        row.addWidget(self._spin_iterations)

        self._btn_run = QPushButton("R&un simulation")
        self._btn_run.setObjectName("btnRunMonteCarloSimulation")
        self._btn_run.clicked.connect(self._on_run_clicked)
        row.addWidget(self._btn_run)
        row.addStretch(1)
        self.body_layout.addLayout(row)

    def _build_description_label(self) -> None:
        self._description_label = QLabel()
        self._description_label.setObjectName("lblMonteCarloDescription")
        self._description_label.setWordWrap(True)
        self.body_layout.addWidget(self._description_label)

    def _build_summary(self) -> None:
        # Why a run is not shown, as a sentence; its figures are a read-out.
        self._error_label = QLabel()
        self._error_label.setObjectName("lblMonteCarloError")
        self._error_label.setWordWrap(True)
        self.body_layout.addWidget(self._error_label)
        self._summary = ReadoutSlot()
        self._summary.setObjectName("lblMonteCarloSummary")
        self.body_layout.addWidget(self._summary)

    def _build_charts(self) -> None:
        self._spaghetti_chart = MonteCarloSpaghettiChartWidget()
        self.body_layout.addWidget(self._spaghetti_chart, 1)
        self._histogram = MonteCarloDrawdownHistogramWidget()
        self.body_layout.addWidget(self._histogram, 1)

    # -- host-facing -------------------------------------------------------

    def refresh(self) -> None:
        snapshot = self._vm.run_result.comparison_snapshot()
        trade_count = len(snapshot.result.trades) if snapshot is not None else 0
        self._btn_run.setEnabled(trade_count >= _MIN_TRADES_REQUIRED)
        self._spin_iterations.setEnabled(trade_count >= _MIN_TRADES_REQUIRED)

        if snapshot is None:
            self._description_label.setText(_NO_RUN_TEXT)
        elif trade_count < _MIN_TRADES_REQUIRED:
            self._description_label.setText(_NOT_ENOUGH_TRADES_TEXT)
        else:
            self._description_label.setText(_READY_TEXT)

        error = self._vm.run_result.monte_carlo_error()
        result = self._vm.run_result.monte_carlo_result()
        if error:
            self._error_label.setText(f"⚠ {error}")
            self._summary.clear()
            self._spaghetti_chart.set_series([])
            self._histogram.set_buckets([])
            return
        self._error_label.setText("")
        if result is None:
            self._summary.clear()
            self._spaghetti_chart.set_series([])
            self._histogram.set_buckets([])
            return
        self._summary.show_readout(build_summary_readout(result))
        self._spaghetti_chart.set_series(
            build_spaghetti_chart_series(result.sample_equity_curves)
        )
        self._histogram.set_buckets(
            build_drawdown_histogram_buckets(result.max_drawdowns_percent)
        )

    # -- running -------------------------------------------------------------

    def _on_run_clicked(self) -> None:
        self._btn_run.setEnabled(False)
        self._vm.requestRunMonteCarlo(self._spin_iterations.value())
