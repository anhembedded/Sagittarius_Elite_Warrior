"""`trading`'s Options page state (`BUG-176`): one row per venue, never a key.

@details The page holds no credential. A row carries a fingerprint (first and last
four characters of the key) and the words of its state; what the user types goes
from the dialog to the use case and nowhere in between.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)


@dataclass(frozen=True)
class KeyRow:
    #: What a row's buttons name when pressed.
    venue: TradingVenue
    title: str
    #: The key's fingerprint and where it is kept; "No key" when there is none.
    key: str
    state: str
    state_is_error: bool
    has_key: bool
    #: Whether Replace and Remove can act: not for a key that is an environment variable.
    editable: bool


class TradingSettingsViewModel(StatusMessageViewModel):
    """@brief State for the Trading settings section."""

    rowsChanged = Signal()
    busyChanged = Signal()

    addKeyRequested = Signal()
    replaceKeyRequested = Signal(object)
    removeKeyRequested = Signal(object)
    checkConnectionsRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: tuple[KeyRow, ...] = ()
        self._busy_text = ""

    @property
    def rows(self) -> tuple[KeyRow, ...]:
        return self._rows

    @Slot(object)
    def set_rows(self, rows: tuple[KeyRow, ...]) -> None:
        self._rows = rows
        self.rowsChanged.emit()

    @property
    def busyText(self) -> str:
        """What is being done, or "" when nothing is."""
        return self._busy_text

    @property
    def busy(self) -> bool:
        return bool(self._busy_text)

    @Slot(str)
    def set_busy(self, text: str) -> None:
        self._busy_text = text
        self.busyChanged.emit()

    @Slot()
    def requestAddKey(self) -> None:
        self.addKeyRequested.emit()

    @Slot(object)
    def requestReplaceKey(self, venue: TradingVenue) -> None:
        self.replaceKeyRequested.emit(venue)

    @Slot(object)
    def requestRemoveKey(self, venue: TradingVenue) -> None:
        self.removeKeyRequested.emit(venue)

    @Slot()
    def requestCheckConnections(self) -> None:
        self.checkConnectionsRequested.emit()
