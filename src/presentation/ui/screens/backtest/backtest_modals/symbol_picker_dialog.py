"""Backtest symbol chooser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

from ._layout import _selectable_grid_card

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class BacktestSymbolPickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỌN SYMBOL", parent=parent)
        self.setObjectName("symbolPickerModal")
        self._vm = view_model
        self.resize(420, 320)

        self._search_field = QLineEdit()
        self._search_field.setObjectName("txtSymbolSearch")
        self._search_field.setPlaceholderText("Tìm symbol (vd: BTC)")
        self._search_field.textChanged.connect(lambda _text: self._sync())
        self.body_layout.addWidget(self._search_field)

        self._loading_label = QLabel("Đang tải danh sách symbol từ sàn...")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 12px;")
        self.body_layout.addWidget(self._loading_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._grid = QGridLayout(content)
        self._grid.setSpacing(8)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)
        self._scroll = scroll

        view_model.symbolOptionsChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        options = list(self._vm.symbolOptions)
        has_options = bool(options)
        self._search_field.setVisible(has_options)
        self._loading_label.setVisible(not has_options)
        self._scroll.setVisible(has_options)

        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        query = self._search_field.text().upper()
        filtered = [s for s in options if not query or query in s]
        for index, symbol in enumerate(filtered):
            is_selected = symbol == self._vm.selectedSymbol
            card = _selectable_grid_card(symbol, is_selected)
            card.setFixedHeight(36)
            card.clicked.connect(lambda s=symbol: self._on_selected(s))
            self._grid.addWidget(card, index // 3, index % 3)

    def _on_selected(self, symbol: str) -> None:
        self._vm.selectedSymbol = symbol
        self.accept()
