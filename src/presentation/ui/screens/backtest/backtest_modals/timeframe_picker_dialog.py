"""Backtest timeframe chooser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QGridLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

from ._layout import _selectable_grid_card

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class TimeframePickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỌN KHUNG THỜI GIAN", parent=parent)
        self.setObjectName("timeframePickerModal")
        self._vm = view_model
        self.resize(380, 240)
        self._grid = QGridLayout()
        self._grid.setSpacing(10)
        self.body_layout.addLayout(self._grid)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        options = list(self._vm.timeframeOptions)
        for index, value in enumerate(options):
            is_selected = value == self._vm.selectedTimeframe
            card = _selectable_grid_card(value, is_selected)
            card.clicked.connect(lambda v=value: self._on_selected(v))
            self._grid.addWidget(card, index // 4, index % 4)

    def _on_selected(self, value: str) -> None:
        self._vm.selectedTimeframe = value
        self.accept()
