"""Backtest engine limitations notice."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class LimitationsDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("GIỚI HẠN CỦA LẦN CHẠY NÀY", parent=parent)
        self.setObjectName("limitationsPopup")
        self._vm = view_model
        self.resize(480, 420)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._list_layout = QVBoxLayout(content)
        self._list_layout.setSpacing(10)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)

        view_model.limitationsChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, text in enumerate(self._vm.limitations):
            row = QHBoxLayout()
            row.setSpacing(10)
            bullet = QLabel("•")
            bullet.setStyleSheet(
                f"color: {Palette.MUTED}; font-size: 13px; font-weight: bold;"
            )
            row.addWidget(bullet)
            label = QLabel(text)
            label.setObjectName(f"lblLimitation_{index}")
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 11px;")
            row.addWidget(label, 1)
            self._list_layout.addLayout(row)
