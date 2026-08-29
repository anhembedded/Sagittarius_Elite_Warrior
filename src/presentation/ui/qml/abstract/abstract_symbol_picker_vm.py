"""Abstract QObject contract shared by standalone symbol-picker VMs."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class AbstractSymbolPickerVM(QObject):
    """Abstract interaction surface exposed to the QML component.

    PySide6 QObject metaclasses do not reliably enforce ``abc.ABC``
    abstractness. The explicit construction guard keeps this base abstract at
    runtime while allowing the concrete VM to remain a normal QObject for QML.
    """

    symbolChosen = Signal(str)
    favouriteToggled = Signal(str)
    favouriteChanged = Signal(str, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        if type(self) is AbstractSymbolPickerVM:
            raise TypeError(
                "AbstractSymbolPickerVM is abstract; instantiate a concrete VM"
            )
        super().__init__(parent)

    @Slot()
    def refresh(self) -> None:
        """Reload source data and rebuild the visible rows."""
        raise NotImplementedError

    @Slot(str)
    def choose(self, symbol: str) -> None:
        """Select a symbol and emit the host-facing command."""
        raise NotImplementedError

    @Slot(str)
    def toggleFavourite(self, symbol: str) -> None:
        """Toggle local state and emit a host-facing favourite command."""
        raise NotImplementedError
