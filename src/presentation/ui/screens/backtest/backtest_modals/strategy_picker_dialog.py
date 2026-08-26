"""Backtest strategy chooser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

from ._layout import _selectable_list_card

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class StrategyPickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỌN CHIẾN LƯỢC BOT", parent=parent)
        self.setObjectName("strategyPickerModal")
        self._vm = view_model
        self.resize(440, 320)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._list_layout = QVBoxLayout(content)
        self._list_layout.setSpacing(8)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for option in self._vm.strategyOptions:
            key = option.get("key", "")
            is_selected = key == self._vm.selectedStrategyKey
            btn = _selectable_list_card(
                "", option.get("name", key), f"Mã: {key}", is_selected
            )
            btn.clicked.connect(lambda _checked=False, k=key: self._on_selected(k))
            self._list_layout.addWidget(btn)

    def _on_selected(self, key: str) -> None:
        self._vm.selectedStrategyKey = key
        self.accept()
