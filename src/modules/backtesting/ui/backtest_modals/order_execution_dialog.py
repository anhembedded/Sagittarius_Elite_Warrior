"""Backtest order-execution settings: when the strategy is evaluated again.

`EPIC-015` §4c hosted `CheckboxList.qml`; `EPIC-025` PR 4.3f replaced it with
`kit.ChecklistOverlay` (ADR D21): four check boxes, two of them mutually
exclusive by a rule only this class knew, and "On bar close" locked checked
so it could only be left by checking its rival. `EPIC-033L` gives the rule
its stock shape: the two exclusive choices are radio buttons
(`ui-presentation-rule.md` §6), so either can be picked; "On order fill" is
a check box beside them; the real-time row stays a locked, checked box, a
fact about live trading this mode cannot change. Changes apply at once, as
they always did, so the only button is Close.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

#: Names the command that opens it: the Run setup's Execution… button.
_TITLE = "Execution"
_ORDER_FILL_TIP = (
    "BOT-077 — re-evaluates the strategy once more at the exact tick an order "
    "just filled, before the next tick, so it can react to its own fill "
    "immediately. Only takes effect in Historical Tick mode; NOT a Stop Loss "
    "fix (BOT-041 already checks every bar regardless of this toggle)."
)
_HISTORICAL_TICK_TIP = (
    "This mode uses 1-second candles, entirely separate from the candles "
    "you've synced at other timeframes — a separate sync of 1-second data "
    "will be required."
)
_REALTIME_TICK_TIP = "Live trading only: a backtest has no real-time bar."
_HISTORICAL_TICK_MODE = "HISTORICAL_TICK"
_BAR_CLOSE_MODE = "BAR_CLOSE"


class OrderExecutionDialog(QDialog):
    """@brief When strategy re-evaluation runs."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setObjectName("orderExecutionModal")
        self.setWindowTitle(_TITLE)

        self.bar_close = QRadioButton("On bar &close")
        self.bar_close.setObjectName("radioExecutionBarClose")
        self.historical_tick = QRadioButton("On every tic&k of the historical bar")
        self.historical_tick.setObjectName("radioExecutionHistoricalTick")
        self.historical_tick.setToolTip(_HISTORICAL_TICK_TIP)
        modes = QButtonGroup(self)
        modes.addButton(self.bar_close)
        modes.addButton(self.historical_tick)
        self.order_fill = QCheckBox("On order fi&ll")
        self.order_fill.setObjectName("chkExecutionOrderFill")
        self.order_fill.setToolTip(_ORDER_FILL_TIP)
        self.realtime_tick = QCheckBox("On every tick of the real-time bar")
        self.realtime_tick.setObjectName("chkExecutionRealtimeTick")
        self.realtime_tick.setToolTip(_REALTIME_TICK_TIP)
        self.realtime_tick.setChecked(True)
        self.realtime_tick.setEnabled(False)

        group = QGroupBox("Evaluate the strategy")
        rows = QVBoxLayout(group)
        for control in (
            self.bar_close,
            self.historical_tick,
            self.order_fill,
            self.realtime_tick,
        ):
            rows.addWidget(control)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.addWidget(buttons)

        self.historical_tick.toggled.connect(self._on_mode_chosen)
        self.order_fill.toggled.connect(self._on_order_fill_toggled)
        view_model.executionModeChanged.connect(self.refresh)
        view_model.calcOnOrderFillsChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        """Shows the view model's execution mode and order-fill flag; a
        change made elsewhere (a reset to idle) never leaves it stale."""
        tick = self._vm.executionMode == _HISTORICAL_TICK_MODE
        for control in (self.bar_close, self.historical_tick, self.order_fill):
            control.blockSignals(True)
        self.historical_tick.setChecked(tick)
        self.bar_close.setChecked(not tick)
        self.order_fill.setChecked(bool(self._vm.calcOnOrderFills))
        for control in (self.bar_close, self.historical_tick, self.order_fill):
            control.blockSignals(False)

    def _on_mode_chosen(self, tick: bool) -> None:
        self._vm.executionMode = _HISTORICAL_TICK_MODE if tick else _BAR_CLOSE_MODE

    def _on_order_fill_toggled(self, checked: bool) -> None:
        self._vm.calcOnOrderFills = checked
