"""Backtest order-execution settings — `EPIC-015` §4c: body is the shared
`CheckboxList`, the fixed-rows-with-a-cross-row-rule variant."""

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

#: The one row a user can actually toggle. Its `key` in `CheckboxListVM.rows`
#: is this index as a string — `CheckboxListVM` does not know these are
#: execution triggers, only that rows have string keys.
_HISTORICAL_TICK_INDEX = 2
_HISTORICAL_TICK_KEY = str(_HISTORICAL_TICK_INDEX)
_BAR_CLOSE_KEY = "0"


class OrderExecutionDialog(QmlOverlay):
    """
    @brief When strategy re-evaluation runs. Chrome is `Overlay`, body is
    `CheckboxList.qml`, rules are `CheckboxListVM` plus one cross-row rule
    this class enforces itself.

    @details `CheckboxListVM` renders whatever `checked`/`locked` state it is
    handed and reports raw toggles — it has no idea two of these four rows
    are mutually exclusive. That rule lives here, in `_rows()` and
    `_on_toggled()`, exactly where the old widget's `_sync()` kept it. Moving
    the *rendering* to QML did not move the *rule* — moving a rule into a
    `.qml` file is the one thing `EPIC-015` §3.2 forbids.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = CheckboxListVM(get_rows=self._rows)
        super().__init__(
            "THỰC THI TẬP LỆNH",
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("orderExecutionModal")
        self.resize(400, 250)
        self._widget_vm.toggled.connect(self._on_toggled)
        view_model.executionModeChanged.connect(self._widget_vm.refresh)

    def showEvent(self, event) -> None:
        self._widget_vm.refresh()
        super().showEvent(event)

    def _rows(self) -> list[dict[str, object]]:
        is_realtime = self._vm.executionMode == "HISTORICAL_TICK"
        # Only these two rows are ever driven by executionMode — the other
        # two have no live source and stay unchecked, matching the widget
        # version's QCheckBox() default that _sync() never touched.
        checked_by_key = {
            _BAR_CLOSE_KEY: not is_realtime,
            _HISTORICAL_TICK_KEY: is_realtime,
        }
        return [
            {
                "key": str(index),
                "label": text,
                "checked": checked_by_key.get(str(index), False),
                "locked": locked,
                "tooltip": tooltip,
            }
            for index, (text, locked, tooltip) in enumerate(_EXECUTION_TRIGGERS)
        ]

    def _on_toggled(self, key: str, checked: bool) -> None:
        if key != _HISTORICAL_TICK_KEY:
            return
        self._vm.executionMode = "HISTORICAL_TICK" if checked else "BAR_CLOSE"
