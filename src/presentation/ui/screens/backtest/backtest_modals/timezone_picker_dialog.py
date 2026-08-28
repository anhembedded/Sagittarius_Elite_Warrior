"""Backtest timezone chooser — `EPIC-015` bậc 1 pilot: body is QML."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimezonePicker.timezone_picker_vm import (
    TimezonePickerVM,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_QML = (
    Path(__file__).resolve().parents[3]
    / "qml"
    / "TimezonePicker"
    / "TimezonePicker.qml"
)


class TimezonePickerDialog(QmlOverlay):
    """
    @brief Which timezone the UI displays. Chrome is `Overlay`, body is
    `TimezonePicker.qml`, rules are `TimezonePickerVM`.

    @details `EPIC-015` bậc 1. The hand-rolled rebuild loop — tear every row
    out of a `QVBoxLayout`, build a `_selectable_list_card` per option, work
    out `is_selected` inline — is a `Repeater` over `vm.rows` now, and
    `selected` is computed in the ViewModel where the gate can see it.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = TimezonePickerVM(
            get_options=lambda: view_model.displayTimezoneOptions,
            get_current=lambda: view_model.displayTimezone,
        )
        super().__init__(
            "CHỌN MÚI GIỜ HIỂN THỊ",
            "Chỉ đổi giờ hiển thị. Dữ liệu và Backtest luôn tính theo UTC.",
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("timezonePickerModal")
        self.resize(440, 350)
        self._widget_vm.chosen.connect(self._on_selected)

    def showEvent(self, event) -> None:
        """Re-reads on every open — the current timezone changes between them,
        and the dialog is built once and reused."""
        self._widget_vm.refresh()
        super().showEvent(event)

    def _on_selected(self, timezone_id: str) -> None:
        self._vm.setDisplayTimezone(timezone_id)
        self.accept()
