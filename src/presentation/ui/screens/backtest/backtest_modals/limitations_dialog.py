"""Backtest engine limitations notice — `EPIC-015` §4c: body is `SelectList`
with `selectable=False`, the read-only-bullet-list shape."""

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


class LimitationsDialog(QmlOverlay):
    """
    @brief Plain-text caveats for the run that just finished. Chrome is
    `Overlay`, body is `SelectList.qml` with `selectable=False`.

    @details Not a separate component: a read-only bullet list is
    `SelectList` with nothing to click, which is what `selectable=False`
    turns off in both the ViewModel (no `selected` ever true, `choose()` is
    a no-op) and the `.qml` (the bullet-row delegate instead of the
    selectable-card one).
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = SelectListVM(
            get_options=lambda: [
                {"id": str(index), "label": text}
                for index, text in enumerate(view_model.limitations)
            ],
            selectable=False,
        )
        super().__init__(
            "GIỚI HẠN CỦA LẦN CHẠY NÀY",
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("limitationsPopup")
        self.resize(480, 420)
        view_model.limitationsChanged.connect(self._widget_vm.refresh)

    def showEvent(self, event) -> None:
        self._widget_vm.refresh()
        super().showEvent(event)
