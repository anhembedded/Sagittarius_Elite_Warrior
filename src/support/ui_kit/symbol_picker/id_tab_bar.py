"""`IdTabBar` — a stock `QTabBar` whose tabs are known by id, not position."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabBar, QWidget


class IdTabBar(QTabBar):
    """@brief A `QTabBar` carrying an id in each tab's `tabData`."""

    #: `(index, id)` of a tab the **user** picked; `show_tabs` never emits it.
    id_selected = Signal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.currentChanged.connect(
            lambda index: self.id_selected.emit(index, str(self.tabData(index)))
        )

    def show_tabs(self, tabs: Sequence[tuple[str, str]], current_id: str) -> None:
        """Shows `tabs` (id, label) with `current_id` selected, without raising
        `id_selected`: only the user's click is a selection."""
        self.blockSignals(True)
        try:
            while self.count():
                self.removeTab(0)
            for tab_id, label in tabs:
                self.setTabData(self.addTab(label), tab_id)
            for index in range(self.count()):
                if self.tabData(index) == current_id:
                    self.setCurrentIndex(index)
                    break
        finally:
            self.blockSignals(False)
