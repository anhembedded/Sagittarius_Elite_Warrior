"""State of the channels group of the Alerts page (`EPIC-036D8`).

The channels this run has, which of them are switched off, whether this copy can change that,
and one line saying why not (or that every channel is off). The view sends the channel and the
box's new state; the presenter is handed the same.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channels_setup import (
    ChannelsState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import channels_words


class ChannelsViewModel(QObject):
    state_changed = Signal()

    #: The owner ticked or cleared a channel: the id, and whether it is now on.
    switch_requested = Signal(str, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._channels: tuple[str, ...] = ()
        self._disabled: frozenset[str] = frozenset()
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
        """Said under the list when it cannot be changed, is empty or has every channel off."""
        return self._note

    def is_on(self, channel_id: str) -> bool:
        return channel_id not in self._disabled

    def take_state(self, state: ChannelsState) -> None:
        self._channels = state.channels
        self._disabled = state.disabled
        self._editable = state.editable
        self._note = self._note_for(state)
        self.state_changed.emit()

    @staticmethod
    def _note_for(state: ChannelsState) -> str:
        if not state.editable:
            return channels_words.READ_ONLY_NOTE
        if not state.channels:
            return channels_words.NO_CHANNELS
        if all(channel in state.disabled for channel in state.channels):
            return channels_words.ALL_OFF
        return ""

    @Slot(str, bool)
    def request_switch(self, channel_id: str, on: bool) -> None:
        self.switch_requested.emit(channel_id, on)
