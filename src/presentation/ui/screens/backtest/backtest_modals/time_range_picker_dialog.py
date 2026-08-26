"""Backtest time-range chooser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

from ._layout import _ACCENT, _FIELD_STYLE, _selectable_list_card

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class TimeRangePickerDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("KHOẢNG THỜI GIAN BACKTEST", parent=parent)
        self.setObjectName("timeRangePickerModal")
        self._vm = view_model
        self.resize(440, 330)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(8)
        self.body_layout.addLayout(self._list_layout)

        self._custom_section = QWidget()
        custom_layout = QVBoxLayout(self._custom_section)
        custom_layout.setContentsMargins(0, 8, 0, 0)
        custom_layout.setSpacing(8)
        hint = QLabel("Nhập khoảng ngày tùy chỉnh:")
        hint.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        custom_layout.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._start_field = QLineEdit()
        self._start_field.setObjectName("txtBacktestRangeStart")
        self._start_field.setPlaceholderText("Từ yyyy-MM-dd HH:mm")
        self._start_field.setStyleSheet(_FIELD_STYLE)
        self._start_field.textEdited.connect(self._on_start_edited)
        row.addWidget(self._start_field)
        self._end_field = QLineEdit()
        self._end_field.setObjectName("txtBacktestRangeEnd")
        self._end_field.setPlaceholderText("Đến yyyy-MM-dd HH:mm")
        self._end_field.setStyleSheet(_FIELD_STYLE)
        self._end_field.textEdited.connect(self._on_end_edited)
        row.addWidget(self._end_field)
        custom_layout.addLayout(row)

        apply_btn = QPushButton("Áp dụng")
        apply_btn.setFixedSize(100, 32)
        apply_btn.setStyleSheet(
            f"background-color: {_ACCENT}; color: {Palette.BG}; font-size: 11px; "
            f"font-weight: bold; border-radius: 6px; border: none;"
        )
        apply_btn.clicked.connect(self.accept)
        custom_row = QHBoxLayout()
        custom_row.addStretch(1)
        custom_row.addWidget(apply_btn)
        custom_layout.addLayout(custom_row)

        self.body_layout.addWidget(self._custom_section)

        view_model.timeRangePresetChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for option in self._vm.timeRangePresetOptions:
            value = option.get("value", "")
            is_selected = value == self._vm.timeRangePreset
            btn = _selectable_list_card("", option.get("label", value), "", is_selected)
            btn.clicked.connect(lambda _checked=False, v=value: self._on_selected(v))
            self._list_layout.addWidget(btn)

        is_custom = self._vm.timeRangePreset == "custom"
        self._custom_section.setVisible(is_custom)
        if is_custom:
            self._start_field.setText(self._vm.customStartText)
            self._end_field.setText(self._vm.customEndText)
            self.resize(440, 410)
        else:
            self.resize(440, 330)

    def _on_selected(self, value: str) -> None:
        self._vm.timeRangePreset = value
        if value != "custom":
            self.accept()

    def _on_start_edited(self, text: str) -> None:
        self._vm.customStartText = text

    def _on_end_edited(self, text: str) -> None:
        self._vm.customEndText = text
