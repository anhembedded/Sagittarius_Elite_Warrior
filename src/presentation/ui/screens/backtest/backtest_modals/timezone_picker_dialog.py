"""Backtest timezone chooser."""

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


class TimezonePickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            "CHỌN MÚI GIỜ HIỂN THỊ",
            "Chỉ đổi giờ hiển thị. Dữ liệu và Backtest luôn tính theo UTC.",
            parent=parent,
        )
        self.setObjectName("timezonePickerModal")
        self._vm = view_model
        self.resize(440, 350)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._list_layout = QVBoxLayout(content)
        self._list_layout.setSpacing(6)
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
        for option in self._vm.displayTimezoneOptions:
            tz_id = option.get("id", "")
            is_selected = tz_id == self._vm.displayTimezone
            btn = _selectable_list_card(
                f"tzItem_{tz_id}", option.get("label", tz_id), "", is_selected
            )
            btn.clicked.connect(lambda _checked=False, t=tz_id: self._on_selected(t))
            self._list_layout.addWidget(btn)

    def _on_selected(self, tz_id: str) -> None:
        self._vm.setDisplayTimezone(tz_id)
        self.accept()
