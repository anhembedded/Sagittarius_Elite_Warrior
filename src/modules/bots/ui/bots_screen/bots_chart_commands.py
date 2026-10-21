"""View → Chart in the Bots mode (`EPIC-040` F1): the chart in front's toolbar by keyboard.

The Live chart's toolbar and the workbench's interval row hold their timeframes as actions, and a
toolbar's buttons take no keyboard focus, so the menu is how a keyboard reaches them
(`ui-presentation-rule.md` §2, §6). Market and Backtest contribute `chart_commands` and keep them in
step with the chart in front through a `ChartCommandMirror`; this does the same for a mode with two
tabs. In front is what the centre shows now:

· the Live tab: the selected bot's chart, with its zoom, Follow latest and More timeframes…;
· the Backtest tab: the workbench's interval row, More timeframes… only (the result chart draws the
  interval that was run and has no timeframe row of its own, `F3`);
· a note in either (no bot, no account yet, a kind with no backtest): every command off.

Presenter-owned (`async-ui-action-rule.md` §2), never registered: parented to the view model by
`bind_bots_commands`.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_command_mirror import (
    ChartCommandMirror,
    chart_command_actions,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    MORE_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .bots_commands import CHART_PREFIX
from .bots_view import BotsView


class BotsChartCommands(QObject):
    """@brief The Bots mode's chart commands, driving and following the chart in front."""

    def __init__(self, view: BotsView, parent: QObject) -> None:
        super().__init__(parent)
        self._view = view
        self._chart = ChartCommandMirror(CHART_PREFIX, self)
        view.front_chart_changed.connect(self._follow_chart_shown)

    def bind_commands(self, binder: ICommandBinder) -> None:
        self._chart.bind_commands(binder)
        self._follow_chart_shown()

    def _follow_chart_shown(self) -> None:
        self._chart.follow_chart(self._front_actions())

    def _front_actions(self) -> Mapping[str, QAction] | None:
        view = self._view
        if view.centre.currentWidget() is view.backtest:
            page = view.shown_backtest_page()
            if isinstance(page, BacktestWorkbenchView):
                return {MORE_TIMEFRAMES: page.interval.timeframes.more_action}
            return None
        card = view.shown_chart()
        return chart_command_actions(card) if isinstance(card, ChartCard) else None
