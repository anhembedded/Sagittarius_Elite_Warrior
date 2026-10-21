"""State of the Quiet hours group of the Alerts page (`EPIC-036D6`).

Words and a few values: whether quiet hours are on, from and to which times, in which zone, and
whether this copy can change them. The times go from the view to the presenter in the two
requests and nowhere in between.
"""

from __future__ import annotations

from datetime import time

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.alerting.application.quiet_hours_setup import (
    QuietHoursState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import quiet_hours_words


class QuietHoursViewModel(QObject):
    state_changed = Signal()

    #: The owner pressed Save with this period.
    period_requested = Signal(object, object)
    #: ... or turned quiet hours off.
    turn_off_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._enabled = False
        self._start = time(22, 0)
        self._end = time(7, 0)
        self._line = ""
        self._editable = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def from_time(self) -> time:
        return self._start

    @property
    def to_time(self) -> time:
        return self._end

    @property
    def line(self) -> str:
        """What is set, in words, with the zone it is read in."""
        return self._line

    @property
    def editable(self) -> bool:
        return self._editable

    def take_state(self, state: QuietHoursState) -> None:
        """Takes what the setup reports; says it in words, or that this copy is read-only."""
        self._enabled = state.enabled
        self._start = state.start
        self._end = state.end
        self._editable = state.editable
        line = quiet_hours_words.zone_line(state)
        self._line = (
            line if state.editable else f"{line} {quiet_hours_words.READ_ONLY_NOTE}"
        )
        self.state_changed.emit()

    @Slot(object, object)
    def request_period(self, start: time, end: time) -> None:
        self.period_requested.emit(start, end)

    @Slot()
    def request_turn_off(self) -> None:
        self.turn_off_requested.emit()
