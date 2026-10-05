"""A running backtest's or sync's progress, in the status bar (`EPIC-033L`).

`ui-presentation-rule.md` §10: modeless progress shows in the status bar, and
an operation with side effects stops with Stop — Tools → Stop backtest, the
mode's command (`backtest_commands.py`), enabled while a run or its sync can
stop. It replaces a banner at the top of the Metrics panel that carried its
own Cancel button, a second way to the same command.

The status bar shows every mode's widgets, so a run's progress stays in view
while the person works in another mode.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QLabel, QProgressBar, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import (
    CANCELLING_CAPTION,
)

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

_RUNNING = "RUNNING"
_SYNCING = "SYNCING"
_CANCELLING = "CANCELLING"
_FULL = 100


def clamp_percent(value: float) -> int:
    """`backtestProgressPercent` and `syncProgressPercent` store whatever
    their setters were given; every real caller clamps first, and the bar
    defends itself too, so a stray value never reads "150%"."""
    return round(min(float(_FULL), max(0.0, value)))


class RunProgressStatus(QObject):
    """The words and the bar; shown only while a run, a sync or its stop
    is under way.

    A `QObject` owned by the view, so the view model's signals reach it
    through bound methods Qt disconnects when the view goes: a view model
    outliving its view never paints into deleted widgets."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.text = QLabel()
        self.text.setObjectName("lblBacktestProgress")
        self.bar = QProgressBar()
        self.bar.setObjectName("prgBacktestProgress")
        self.bar.setRange(0, _FULL)
        self._view_model: BackTestViewModel | None = None
        self._set_progress_visible(False)

    @property
    def widgets(self) -> Sequence[QWidget]:
        return (self.text, self.bar)

    def track_run_of(self, view_model: BackTestViewModel) -> None:
        self._view_model = view_model
        view_model.uiModeChanged.connect(self._sync_run_progress)
        view_model.run_progress.backtestProgressChanged.connect(self._sync_run_progress)
        view_model.run_progress.syncProgressChanged.connect(self._sync_run_progress)
        self._sync_run_progress()

    def _sync_run_progress(self) -> None:
        vm = self._view_model
        if vm is None:
            return
        mode = vm.uiMode
        self._set_progress_visible(mode in (_RUNNING, _SYNCING, _CANCELLING))
        progress = vm.run_progress
        if mode == _CANCELLING:
            self.text.setText(CANCELLING_CAPTION)
            self.bar.setRange(0, 0)
            return
        self.bar.setRange(0, _FULL)
        # The view model's fields are Qt `Property`s, which mypy cannot read
        # through (`EPIC-002D`); they are read by name.
        if mode == _SYNCING:
            self._show_progress(progress, "syncProgressText", "syncProgressPercent")
        elif mode == _RUNNING:
            self._show_progress(
                progress, "backtestProgressText", "backtestProgressPercent"
            )

    def _show_progress(self, progress: QObject, text: str, percent: str) -> None:
        self.text.setText(str(progress.property(text)))
        self.bar.setValue(clamp_percent(float(progress.property(percent))))

    def _set_progress_visible(self, visible: bool) -> None:
        self.text.setVisible(visible)
        self.bar.setVisible(visible)
