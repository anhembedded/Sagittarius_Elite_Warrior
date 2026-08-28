"""Backtest timezone chooser — `EPIC-015` bậc 2: body is the shared `SelectList`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SelectList.select_list_vm import (
    SelectListVM,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_QML = Path(__file__).resolve().parents[3] / "qml" / "SelectList" / "SelectList.qml"


class TimezonePickerDialog(QmlOverlay):
    """
    @brief Which timezone the UI displays. Chrome is `Overlay`, body is the
    shared `SelectList.qml`, rules are `SelectListVM`.

    @details `EPIC-015` §4c. Was its own `TimezonePicker.qml` +
    `TimezonePickerVM` in bậc 1 — deleted here, not kept as a forwarder,
    after counting the remaining modals turned up `strategy_picker_dialog`
    doing the exact same shape with a different title. One component now
    serves both, plus the read-only variant `limitations_dialog` uses.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = SelectListVM(
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
