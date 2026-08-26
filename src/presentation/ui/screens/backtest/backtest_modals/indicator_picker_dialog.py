"""Backtest indicator multi-select."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class IndicatorPickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỈ BÁO THAM KHẢO", parent=parent)
        self.setObjectName("indicatorPickerModal")
        self._vm = view_model
        self.resize(360, 300)

        self._empty_label = QLabel("Chưa có tập lệnh chỉ báo nào được đăng ký.")
        self._empty_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        self.body_layout.addWidget(self._empty_label)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(8)
        self.body_layout.addLayout(self._list_layout)

        view_model.script_model.modelReset.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        model = self._vm.script_model
        row_count = model.rowCount()
        self._empty_label.setVisible(row_count == 0)
        for row in range(row_count):
            index = model.index(row, 0)
            key = model.data(index, model.KeyRole)
            title = model.data(index, model.TitleRole)
            enabled = bool(model.data(index, model.EnabledRole))
            checkbox = QCheckBox(title)
            checkbox.setObjectName(f"chkBacktestScript_{key}")
            checkbox.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 12px;")
            checkbox.setChecked(enabled)
            checkbox.toggled.connect(
                lambda checked, r=row: model.setEnabled(r, checked)
            )
            self._list_layout.addWidget(checkbox)
