"""Backtest indicator multi-select — the shared `ChecklistOverlay`, wired to a
live model.

`EPIC-015` §4c hosted `CheckboxList.qml` here; `EPIC-025` PR 4.3f replaced it
with `kit.ChecklistOverlay` (ADR D21), the shape `PickerOverlay` had declined to
serve. Rows come from a live `IndicatorScriptListModel`, unlike
`OrderExecutionDialog`'s fixed four — `key` is the model's real `KeyRole`, and
toggling writes straight back through `model.setEnabled()`. No row is ever
locked here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    ChecklistItem,
    ChecklistOverlay,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "REFERENCE INDICATORS"
#: The `.qml` this replaces rendered nothing at all with zero scripts — a blank
#: box that reads as "loading" rather than "there are none", which is the
#: distinction `ui-presentation-rule`'s UX principles ask an empty state to
#: make. The QtWidgets version this replaced *did* have a label; it came back.
_EMPTY_TEXT = "No indicator scripts are registered."


class IndicatorPickerDialog(ChecklistOverlay):
    """@brief Which indicator scripts draw on the chart."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        super().__init__(_TITLE, empty_text=_EMPTY_TEXT, parent=parent)
        self.setObjectName("indicatorPickerModal")
        self.resize(360, 300)
        self.toggled.connect(self._on_toggled)
        view_model.script_model.modelReset.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Re-reads the script model. Called on every open and on every model
        reset: the registered set changes while this dialog exists."""
        model = self._vm.script_model
        rows = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            rows.append(
                ChecklistItem(
                    key=str(model.data(index, model.KeyRole)),
                    label=str(model.data(index, model.TitleRole)),
                    checked=bool(model.data(index, model.EnabledRole)),
                )
            )
        self.set_items(rows)

    def _on_toggled(self, key: str, checked: bool) -> None:
        model = self._vm.script_model
        for row in range(model.rowCount()):
            if str(model.data(model.index(row, 0), model.KeyRole)) == key:
                model.setEnabled(row, checked)
                return
