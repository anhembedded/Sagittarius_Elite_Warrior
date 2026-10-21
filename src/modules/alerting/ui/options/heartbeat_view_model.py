"""State of the heartbeat group of the Alerts page (`EPIC-036D9`).

The interval in force, what may be chosen, and whether this copy can change it. The view sends
the hours as a number and the presenter is handed the same.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_setup import (
    HeartbeatState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import heartbeat_words


class HeartbeatViewModel(QObject):
    state_changed = Signal()

    #: The owner chose an interval: whole hours.
    hours_requested = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hours = 0
        self._offered: tuple[int, ...] = ()
        self._editable = True

    @property
    def hours(self) -> int:
        return self._hours

    @property
    def offered_hours(self) -> tuple[int, ...]:
        return self._offered

    @property
    def editable(self) -> bool:
        return self._editable

    @property
    def note(self) -> str:
        """Said under the choice when it cannot be changed; "" otherwise."""
        return "" if self._editable else heartbeat_words.READ_ONLY_NOTE

    def take_state(self, state: HeartbeatState) -> None:
        self._hours = state.hours
        self._offered = state.choices
        self._editable = state.editable
        self.state_changed.emit()

    @Slot(int)
    def request_hours(self, hours: int) -> None:
        self.hours_requested.emit(hours)
