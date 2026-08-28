"""Backtest indicator multi-select — `EPIC-015` §4c: body is the shared
`CheckboxList`, the live-model variant."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.CheckboxList.checkbox_list_vm import (
    CheckboxListVM,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_QML = Path(__file__).resolve().parents[3] / "qml" / "CheckboxList" / "CheckboxList.qml"


class IndicatorPickerDialog(QmlOverlay):
    """
    @brief Which indicator scripts draw on the chart. Chrome is `Overlay`,
    body is `CheckboxList.qml`, rules are `CheckboxListVM`.

    @details Rows come from a live `IndicatorScriptListModel`, unlike
    `OrderExecutionDialog`'s fixed four — `key` here is the model's real
    `KeyRole`, and toggling writes straight back through `model.setEnabled()`.
    No row is ever locked; `"Chưa có tập lệnh chỉ báo nào được đăng ký."`
    (the old empty-state label) is not reproduced here because an empty
    `CheckboxList` already renders nothing, which reads the same way a
    picker with zero registered scripts should.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = CheckboxListVM(get_rows=self._rows)
        super().__init__(
            "CHỈ BÁO THAM KHẢO",
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("indicatorPickerModal")
        self.resize(360, 300)
        self._widget_vm.toggled.connect(self._on_toggled)
        view_model.script_model.modelReset.connect(self._widget_vm.refresh)

    def showEvent(self, event) -> None:
        self._widget_vm.refresh()
        super().showEvent(event)

    def _rows(self) -> list[dict[str, object]]:
        model = self._vm.script_model
        rows = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            rows.append(
                {
                    "key": model.data(index, model.KeyRole),
                    "label": model.data(index, model.TitleRole),
                    "checked": bool(model.data(index, model.EnabledRole)),
                }
            )
        return rows

    def _on_toggled(self, key: str, checked: bool) -> None:
        model = self._vm.script_model
        for row in range(model.rowCount()):
            if model.data(model.index(row, 0), model.KeyRole) == key:
                model.setEnabled(row, checked)
                return
