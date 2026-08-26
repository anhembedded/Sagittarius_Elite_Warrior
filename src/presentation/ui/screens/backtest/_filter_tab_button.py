"""One filter tab in the trade-logs panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
)


class _FilterTabButton(QPushButton):
    def __init__(self, value: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.value = value
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.STATE_HOVER_BG if active else 'transparent'}; "
            f"border: 1px solid {Palette.STATE_NAV_BORDER if active else 'transparent'}; border-radius: 6px; "
            f"color: {Palette.TEXT_PRIMARY if active else Palette.MUTED}; font-size: 11px; "
            f"font-weight: {'bold' if active else 'normal'}; padding: 0 10px; }}"
        )
