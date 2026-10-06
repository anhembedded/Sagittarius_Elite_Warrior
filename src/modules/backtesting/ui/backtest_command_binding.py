"""How the Backtest mode performs its commands (`EPIC-033D`): each to the
view-model request its button used to make. The commands themselves are
declared Qt-free in `backtest_commands.py`."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState

from .backtest_commands import (
    COMPARE_REPORTS,
    EXPORT_TRADES,
    IMPORT_REPORT,
    MONTE_CARLO,
    OUT_OF_SAMPLE,
    RUN,
    SAVE_REPORT,
    STOP,
)
from .backtest_view_model import BackTestViewModel
from .chart_display_commands import ChartDisplayCommands, front_chart
from .ports.i_backtest_view import IBacktestView

#: The modes a run or its sync can be stopped in; CANCELLING is already stopping.
_STOPPABLE_MODES = frozenset({"RUNNING", "SYNCING"})


def bind_backtest_commands(
    binder: ICommandBinder,
    view_model: BackTestViewModel,
    view: IBacktestView,
) -> None:
    """What `BackTestPresenter.bind_commands` binds. View → Chart follows
    the chart `view` draws now, its toolbar and its card, and each one drawn
    after it (`BOT-155`, `BOT-156`, `ChartDisplayCommands.follow_controls_of`)."""
    display = ChartDisplayCommands(view_model)
    display.bind_commands(binder)
    display.follow_toolbar(view.chart_controls, front_chart(view.chart_cards))
    idle = DerivedState(
        view_model.controlsEnabledChanged,
        lambda: bool(view_model.controlsEnabled),
        view_model,
    )
    stoppable = DerivedState(
        view_model.uiModeChanged,
        lambda: view_model.uiMode in _STOPPABLE_MODES,
        view_model,
    )
    has_result = DerivedState(
        view_model.run_result.statCardsChanged,
        lambda: bool(view_model.run_result.primaryStatCards),
        view_model,
    )
    while_idle: dict[str, Callable[[], None]] = {
        RUN: view_model.requestRun,
        IMPORT_REPORT: view_model.requestImportReport,
        COMPARE_REPORTS: view_model.requestOpenCompareReports,
        OUT_OF_SAMPLE: view_model.requestOpenOutOfSampleComparison,
        MONTE_CARLO: view_model.requestOpenMonteCarlo,
    }
    for command_id, request in while_idle.items():
        _bind(binder, command_id, request, idle)
    _bind(binder, STOP, view_model.requestCancelBacktest, stoppable)
    _bind(binder, SAVE_REPORT, view_model.requestExportReport, has_result)
    trades_listed = DerivedState(
        view_model.trade_log.rowsChanged,
        lambda: bool(view_model.trade_log.rows),
        view_model,
    )
    _bind(binder, EXPORT_TRADES, view_model.trade_log.request_export, trades_listed)


def _bind(
    binder: ICommandBinder,
    command_id: str,
    request: Callable[[], None],
    state: DerivedState,
) -> None:
    def run(_checked: bool) -> None:
        request()

    binder.bind(command_id, run, enabled=state.changed, initially_enabled=state.value)
