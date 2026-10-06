"""A ViewModel's status line — one message plus whether it reads as an
error — and the property/signal wiring every consumer needed identically.

The two readers are plain Python properties and `statusChanged` is the change
notification: no `QtCore.Property` is declared, and the class is a plain
`QObject`, not the Engine's `BaseQmlViewModel`, whose two Properties it
inherited unused (`BUG-152`).

`DeskViewModel`, `TradingSettingsViewModel` and `MarketDataSettingsViewModel`
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

from PySide6.QtCore import QObject, Signal, Slot


class StatusMessageViewModel(QObject):
    """@brief A single status line (message + error flag) a screen's
    ViewModel shows after a save or another user-triggered action
    completes."""

    statusChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status_message = ""
        self._status_is_error = False

    @property
    def statusMessage(self) -> str:
        return self._status_message

    @property
    def statusIsError(self) -> bool:
        return self._status_is_error

    @Slot(str, bool)
    def set_status(self, message: str, is_error: bool) -> None:
        self._status_message = message
        self._status_is_error = is_error
        self.statusChanged.emit()
