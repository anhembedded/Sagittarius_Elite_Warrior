"""A ViewModel's status line — one message plus whether it reads as an
error — and the property/signal wiring every consumer needed identically.

`TradingViewModel`, `TradingSettingsViewModel` and `MarketDataSettingsViewModel`
all defined `set_status()`/`_get_status_message()`/`_get_status_is_error()`
byte-for-byte before this class existed — three copies of a four-line
pattern, exactly the class of duplication
`tools/measure_duplicate_members.py` exists to catch
(`tests/unit/architecture/test_presenter_duplication_only_shrinks.py`). A
member name a package inherits from a shared base under `support/`/`core/`
is not counted against that ratchet — the tool's own documented amendment —
so this is the general fix the guard's docstring asks for, not a baseline
raise.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel


class StatusMessageViewModel(BaseQmlViewModel):
    """@brief A single status line (message + error flag) a screen's
    ViewModel shows after a save or another user-triggered action
    completes."""

    statusChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status_message = ""
        self._status_is_error = False

    def _get_status_message(self) -> str:
        return self._status_message

    statusMessage = Property(str, _get_status_message, notify=statusChanged)

    def _get_status_is_error(self) -> bool:
        return self._status_is_error

    statusIsError = Property(bool, _get_status_is_error, notify=statusChanged)

    @Slot(str, bool)
    def set_status(self, message: str, is_error: bool) -> None:
        self._status_message = message
        self._status_is_error = is_error
        self.statusChanged.emit()
