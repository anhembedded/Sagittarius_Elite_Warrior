"""View → Chart (`BOT-155`): the chart mode and the three layers as commands,
in step with the chart's own toolbar.

The toolbar (`BacktestChartControls`) holds one action per choice, but a
toolbar's buttons take no keyboard focus, so the menu is how a keyboard
reaches them (`ui-presentation-rule.md` §2, §6). The menu's actions are the
shell's; this object keeps the two in step without a second copy of the
state: a menu command drives the toolbar's action, and the toolbar's action
says back whether it is checked and enabled. Before a result is drawn there
is no toolbar, and every command is off.

Presenter-owned (`async-ui-action-rule.md` §2), never registered: bound with
the mode's other commands, it follows the toolbar drawn at that moment, and
is parented to the presenter's view model. The view rebuilds the toolbar
with every symbol it draws; `follow_controls_of()` hands each new one over.

The chart card's own toolbar (zoom, Follow latest, More timeframes…) is in the
same submenu (`BOT-156`), kept in step by a `ChartCommandMirror` that
follows the first card, the one the chart toolbar above it drives.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.support.charting.chart_command_mirror import (
    ChartCommandMirror,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .backtest_commands import (
    CHART_PREFIX,
    SHOW_CANDLESTICK,
    SHOW_EQUITY,
    SHOW_INDICATORS,
    SHOW_SIDE_BY_SIDE,
    SHOW_TRADE_FLAGS,
    SHOW_VOLUME,
)
from .logic.chart_canvas_view import ChartDisplayMode
from .logic.chart_controls import LAYER_INDICATORS, LAYER_TRADE_FLAGS, LAYER_VOLUME
from .ports.i_backtest_chart_controls import IBacktestChartControls
from .ports.i_backtest_chart_host import IBacktestChartHost

#: Command -> the key of the toolbar action it drives.
_DRIVES: Mapping[str, str] = {
    SHOW_CANDLESTICK: ChartDisplayMode.OHLC.value,
    SHOW_EQUITY: ChartDisplayMode.EQUITY.value,
    SHOW_SIDE_BY_SIDE: ChartDisplayMode.BOTH.value,
    SHOW_INDICATORS: LAYER_INDICATORS,
    SHOW_VOLUME: LAYER_VOLUME,
    SHOW_TRADE_FLAGS: LAYER_TRADE_FLAGS,
}


def front_chart(cards: Sequence[IBacktestChartHost]) -> IBacktestChartHost | None:
    """The card the chart toolbar drives: the first, when any is drawn."""
    return cards[0] if cards else None


class _CommandState(QObject):
    """What the shell's action for one command shows."""

    checked = Signal(bool)
    enabled = Signal(bool)


class ChartDisplayCommands(QObject):
    """@brief View → Chart, driving and following the chart's toolbar."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._states = {key: _CommandState(self) for key in _DRIVES.values()}
        self._actions: Mapping[str, QAction] = {}
        self._chart = ChartCommandMirror(CHART_PREFIX, self)

    @classmethod
    def follow_controls_of(
        cls,
        owner: QObject,
        controls: IBacktestChartControls | None,
        chart: IBacktestChartHost | None = None,
    ) -> None:
        """Hands the toolbar and the chart the view just built to the
        commands `owner` (the presenter's view model) holds."""
        for commands in owner.findChildren(
            cls, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            commands.follow_toolbar(controls, chart)

    def bind_commands(self, binder: ICommandBinder) -> None:
        for command_id, key in _DRIVES.items():
            state = self._states[key]
            binder.bind(
                command_id,
                partial(self._on_command, key),
                enabled=state.enabled,
                checked=state.checked,
                initially_enabled=False,
            )
        self._chart.bind_commands(binder)

    def follow_toolbar(
        self,
        controls: IBacktestChartControls | None,
        chart: IBacktestChartHost | None = None,
    ) -> None:
        """Follows `controls`' actions and `chart`'s; none means no chart,
        every command off."""
        self._chart.follow_chart(chart.command_actions() if chart is not None else None)
        self._actions = controls.display_actions() if controls is not None else {}
        for key, state in self._states.items():
            action = self._actions.get(key)
            if action is None:
                state.enabled.emit(False)
                continue
            action.toggled.connect(state.checked.emit)
            action.enabledChanged.connect(state.enabled.emit)
            state.checked.emit(action.isChecked())
            state.enabled.emit(action.isEnabled())

    def _on_command(self, key: str, checked: bool) -> None:
        action = self._actions.get(key)
        if action is None or not action.isEnabled():
            return
        if action.actionGroup() is not None:
            # A choice: picking the one already shown changes nothing.
            if not action.isChecked():
                action.trigger()
        elif action.isChecked() != checked:
            action.setChecked(checked)
