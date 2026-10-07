"""`EPIC-034G` — what a chart says about being live, and its one command.

A label with the state's words (Error carries its reason; Live carries the age
of the last update) and a tool button for the command that state offers. The
button shows a `QAction`, so the chart's context menu repeats the same
command. It holds no lifecycle: `LiveCandleChart` tells it the state, and it
reports the command the user chose.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    COMMAND_WORDS,
    STATE_COMMAND,
    STATE_WORDS,
    LiveChartState,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

#: How often the age of the last update is written again, while Live.
AGE_REFRESH_MS = 1000

#: Longest an error reason is written in the chip; the tooltip has it whole.
_REASON_CHARS = 60

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600


def age_text(seconds: float | None) -> str:
    """How long ago the last update was; `None` means none has come yet."""
    if seconds is None:
        return "waiting for the first update"
    whole = max(0, int(seconds))
    if whole < _SECONDS_PER_MINUTE:
        return f"updated {whole} s ago"
    if whole < _SECONDS_PER_HOUR:
        return f"updated {whole // _SECONDS_PER_MINUTE} min ago"
    return f"updated {whole // _SECONDS_PER_HOUR} h ago"


def _short(reason: str) -> str:
    if len(reason) <= _REASON_CHARS:
        return reason
    return reason[: _REASON_CHARS - 1].rstrip() + "…"


class LiveStateChip(QWidget):
    """@brief The words of a chart's live state and its command."""

    #: The user chose the command the state offers.
    commandRequested = Signal(object)

    def __init__(
        self,
        age_seconds: Callable[[], float | None],
        parent: QWidget | None = None,
    ) -> None:
        """@param age_seconds Seconds since the chart's last update, `None`
        before the first; asked while the chip shows Live."""
        super().__init__(parent)
        self._age_seconds = age_seconds
        self._state = LiveChartState.HISTORY
        self._reason = ""
        self.setObjectName("liveStateChip")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self._label = plain_label()
        self._label.setObjectName("liveStateLabel")
        row.addWidget(self._label)
        self.command = QAction(self)
        self.command.setObjectName("act_liveCommand")
        self.command.triggered.connect(self._on_triggered)
        button = QToolButton()
        button.setObjectName("liveCommandButton")
        button.setDefaultAction(self.command)
        row.addWidget(button)
        self._timer = QTimer(self)
        self._timer.setInterval(AGE_REFRESH_MS)
        self._timer.timeout.connect(self._write)
        self.show_state(LiveChartState.HISTORY, "")

    @property
    def state(self) -> LiveChartState:
        return self._state

    @property
    def text(self) -> str:
        """What the chip says now."""
        return self._label.text()

    def show_state(self, state: LiveChartState, reason: str) -> None:
        self._state = state
        self._reason = reason
        self.command.setText(COMMAND_WORDS[STATE_COMMAND[state]])
        if state is LiveChartState.LIVE:
            self._timer.start()
        else:
            self._timer.stop()
        self._write()

    def _write(self) -> None:
        words = STATE_WORDS[self._state]
        tip = ""
        if self._state is LiveChartState.LIVE:
            words = f"{words} · {age_text(self._age_seconds())}"
        elif self._state is LiveChartState.ERROR:
            tip = self._reason
            words = f"{words}: {_short(self._reason)}" if self._reason else words
        self._label.setText(words)
        self._label.setToolTip(tip)

    def _on_triggered(self) -> None:
        self.commandRequested.emit(STATE_COMMAND[self._state])
