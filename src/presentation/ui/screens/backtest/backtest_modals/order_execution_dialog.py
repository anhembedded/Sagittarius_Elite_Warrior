"""Backtest order-execution settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


_EXECUTION_TRIGGERS = (
    ("On bar close", True, ""),
    ("Khi lệnh được khớp", True, ""),
    (
        "Trên mỗi tick của thanh lịch sử",
        False,
        (
            "Chế độ này dùng nến 1 giây, tách biệt hoàn toàn với nến bạn đã đồng bộ ở khung "
            "thời gian khác — sẽ cần đồng bộ lại dữ liệu riêng cho khung 1 giây."
        ),
    ),
    ("Trên mỗi tick của thanh thời gian thực", True, ""),
)

_HISTORICAL_TICK_INDEX = 2


class OrderExecutionDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("THỰC THI TẬP LỆNH", parent=parent)
        self.setObjectName("orderExecutionModal")
        self._vm = view_model
        self.resize(400, 250)

        self._checkboxes: list[QCheckBox] = []
        for index, (text, locked, tooltip) in enumerate(_EXECUTION_TRIGGERS):
            row = QHBoxLayout()
            row.setSpacing(10)
            checkbox = QCheckBox()
            checkbox.setObjectName(f"triggerCheckBox_{index}")
            checkbox.setEnabled(not locked)
            row.addWidget(checkbox)
            label = QLabel(text)
            label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 12px;")
            row.addWidget(label, 1)
            if tooltip:
                label.setToolTip(tooltip)
                checkbox.setToolTip(tooltip)
            container = QWidget()
            container.setObjectName(f"chkExecutionTrigger_{index}")
            container.setLayout(row)
            self.body_layout.addWidget(container)
            checkbox.toggled.connect(
                lambda checked, i=index: self._on_toggled(i, checked)
            )
            self._checkboxes.append(checkbox)

        view_model.executionModeChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        is_realtime = self._vm.executionMode == "HISTORICAL_TICK"
        for checkbox in self._checkboxes:
            checkbox.blockSignals(True)
        self._checkboxes[0].setChecked(not is_realtime)
        self._checkboxes[_HISTORICAL_TICK_INDEX].setChecked(is_realtime)
        for checkbox in self._checkboxes:
            checkbox.blockSignals(False)

    def _on_toggled(self, index: int, checked: bool) -> None:
        if index != _HISTORICAL_TICK_INDEX:
            return
        self._vm.executionMode = "HISTORICAL_TICK" if checked else "BAR_CLOSE"
