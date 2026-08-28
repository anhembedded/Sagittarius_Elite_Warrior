"""Backtest strategy chooser — `EPIC-015` §4c: body is the shared `SelectList`."""

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


class StrategyPickerDialog(QmlOverlay):
    """
    @brief Which strategy the run uses. Chrome is `Overlay`, body is the
    shared `SelectList.qml`, rules are `SelectListVM`.

    @details Same shape as `TimezonePickerDialog` — the subtitle
    ("Mã: <key>") is what `SelectListVM.rows()` already exposes as
    `subtitle`, so nothing here is special-cased for it.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = SelectListVM(
            get_options=lambda: [
                {
                    "id": option.get("key", ""),
                    "label": option.get("name", option.get("key", "")),
                    "subtitle": f"Mã: {option.get('key', '')}",
                }
                for option in view_model.strategyOptions
            ],
            get_current=lambda: view_model.selectedStrategyKey,
        )
        super().__init__(
            "CHỌN CHIẾN LƯỢC BOT",
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("strategyPickerModal")
        self.resize(440, 320)
        self._widget_vm.chosen.connect(self._on_selected)

    def showEvent(self, event) -> None:
        self._widget_vm.refresh()
        super().showEvent(event)

    def _on_selected(self, key: str) -> None:
        self._vm.selectedStrategyKey = key
        self.accept()
