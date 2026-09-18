"""`EPIC-003F5a` — the Backtest screen's two progress bars, lifted out of
`BackTestViewModel`.

@details Fifth slice of `EPIC-003F` (first half), under the same rule as
`003F1`–`003F4`: this class owns the state, `BackTestViewModel` forwards to
it, and **no call site changes**.

@par Why two bars and not one
They report two different long jobs that can be in flight at the same
time: a backtest run, and a data sync started from the "Đồng bộ ngay"
affordance. Collapsing them into one pair of fields would make a sync
finishing look like the run finishing.

@par `reset_*` is not `set_*(0, "")` spelled twice
It is the same call, deliberately — but named, so a caller resetting a bar
cannot accidentally reset it to a *non-*empty text and leave a stale
"Đang chạy…" under a 0% bar.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

#: What "no job running" looks like on either bar.
IDLE_PERCENT = 0.0
IDLE_TEXT = ""


class RunProgressViewModel(QObject):
    """@brief How far along the backtest run and the data sync are."""

    #: Both fields of a bar move together and are read together, so one
    #: signal per bar (not per field) — two emits for one update is how a
    #: widget ends up rendering a percent from one job and a caption from
    #: the previous one.
    backtestProgressChanged = Signal()
    syncProgressChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backtest_percent = IDLE_PERCENT
        self._backtest_text = IDLE_TEXT
        self._sync_percent = IDLE_PERCENT
        self._sync_text = IDLE_TEXT

    # ------------------------------------------------------------------ #
    # Backtest run
    # ------------------------------------------------------------------ #

    def _get_backtest_percent(self) -> float:
        return self._backtest_percent

    backtestProgressPercent = Property(
        float, _get_backtest_percent, notify=backtestProgressChanged
    )

    def _get_backtest_text(self) -> str:
        return self._backtest_text

    backtestProgressText = Property(
        str, _get_backtest_text, notify=backtestProgressChanged
    )

    @Slot(float, str)
    def set_backtest_progress(self, percent: float, text: str) -> None:
        self._backtest_percent = percent
        self._backtest_text = text
        self.backtestProgressChanged.emit()

    @Slot()
    def reset_backtest_progress(self) -> None:
        self.set_backtest_progress(IDLE_PERCENT, IDLE_TEXT)

    # ------------------------------------------------------------------ #
    # Data sync
    # ------------------------------------------------------------------ #

    def _get_sync_percent(self) -> float:
        return self._sync_percent

    syncProgressPercent = Property(float, _get_sync_percent, notify=syncProgressChanged)

    def _get_sync_text(self) -> str:
        return self._sync_text

    syncProgressText = Property(str, _get_sync_text, notify=syncProgressChanged)

    @Slot(float, str)
    def set_sync_progress(self, percent: float, text: str) -> None:
        self._sync_percent = percent
        self._sync_text = text
        self.syncProgressChanged.emit()

    @Slot()
    def reset_sync_progress(self) -> None:
        self.set_sync_progress(IDLE_PERCENT, IDLE_TEXT)
