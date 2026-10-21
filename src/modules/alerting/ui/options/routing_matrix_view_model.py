"""State of the routing matrix group of the Alerts page (`EPIC-036D7`).

The columns (the channels this run has), what the owner chose in each cell, whether this copy can
change it, and one line saying why not. A cell value is the text of a `Loudness`, or empty for the
default: the view sends text and the presenter makes the enum again (a `str`-based enum comes back
from a combo as a plain `str`, `BUG-144`).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.alerting.application.routing_setup import (
    RoutingState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import routing_words


class RoutingMatrixViewModel(QObject):
    state_changed = Signal()

    #: The owner chose a value in a cell: the group, the channel, and a `Loudness` or `None`
    #: for the default.
    cell_requested = Signal(object, str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._channels: tuple[str, ...] = ()
        self._chosen: dict[tuple[str, str], str] = {}
        self._editable = True
        self._note = ""

    @property
    def channels(self) -> tuple[str, ...]:
        return self._channels

    @property
    def editable(self) -> bool:
        return self._editable

    @property
    def note(self) -> str:
        """Said under the matrix when it cannot be shown or changed; "" otherwise."""
        return self._note

    def cell_value(self, group: AlertGroup, channel_id: str) -> str:
        """The cell's value: a `Loudness` text, or empty for its default."""
        return self._chosen.get((group.value, channel_id), routing_words.DEFAULT_VALUE)

    def take_state(self, state: RoutingState) -> None:
        self._channels = state.channels
        self._chosen = {
            (group.value, channel_id): loudness.value
            for (group, channel_id), loudness in state.chosen.items()
        }
        self._editable = state.editable
        if not state.editable:
            self._note = routing_words.READ_ONLY_NOTE
        else:
            self._note = "" if state.channels else routing_words.NO_CHANNELS
        self.state_changed.emit()

    @Slot(str, str, str)
    def request_cell(self, group: str, channel_id: str, value: str) -> None:
        """Takes the view's text and says it as the enums; an unknown text is ignored."""
        try:
            loudness = Loudness(value) if value else None
            cell = AlertGroup(group)
        except ValueError:
            return
        self.cell_requested.emit(cell, channel_id, loudness)
