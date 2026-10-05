"""Backtest indicator multi-select: which indicator scripts draw on the chart.

`EPIC-015` §4c hosted `CheckboxList.qml` here; `EPIC-025` PR 4.3f replaced it
with `kit.ChecklistOverlay` (ADR D21). `EPIC-033L` makes it a stock `QDialog`:
one check box per script of the live `IndicatorScriptListModel`, and Close.
A check box writes straight back through `model.setEnabled()`, so there is
nothing to commit. The registered set changes while the dialog exists, so it
is rebuilt on every open and every model reset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

#: Names the command that opens it: the Run setup's Indicators… button.
_TITLE = "Indicators"
#: A blank box reads as "loading" rather than "there are none".
_EMPTY_TEXT = "No indicator scripts are registered."


class IndicatorPickerDialog(QDialog):
    """@brief Which indicator scripts draw on the chart."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setObjectName("indicatorPickerModal")
        self.setWindowTitle(_TITLE)
        self._rows = QWidget()
        self._rows_layout = QVBoxLayout(self._rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        # The registry grows; the list scrolls, the dialog does not (review
        # of PR #362).
        scroll = QScrollArea()
        scroll.setObjectName("indicatorScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._rows)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)
        view_model.script_model.modelReset.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def check_boxes(self) -> list[QCheckBox]:
        return self._rows.findChildren(QCheckBox)

    def refresh(self) -> None:
        """One check box per registered script, checked while it draws."""
        while self._rows_layout.count():
            entry = self._rows_layout.takeAt(0)
            widget = entry.widget() if entry is not None else None
            if widget is not None:
                # Detached now, not only on the deferred delete, so a rebuild
                # never shows the previous rows beside the new ones.
                widget.setParent(None)
                widget.deleteLater()
        model = self._vm.script_model
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            key = str(model.data(index, model.KeyRole))
            # A script's title is text, never an access key.
            title = str(model.data(index, model.TitleRole)).replace("&", "&&")
            box = QCheckBox(title)
            box.setObjectName(f"chkIndicator_{key}")
            box.setChecked(bool(model.data(index, model.EnabledRole)))
            box.toggled.connect(
                lambda checked, script=key: self._on_toggled(script, checked)
            )
            self._rows_layout.addWidget(box)
        if model.rowCount() == 0:
            empty = QLabel(_EMPTY_TEXT)
            empty.setObjectName("lblIndicatorsEmpty")
            self._rows_layout.addWidget(empty)

    def _on_toggled(self, key: str, checked: bool) -> None:
        model = self._vm.script_model
        for row in range(model.rowCount()):
            if str(model.data(model.index(row, 0), model.KeyRole)) == key:
                model.setEnabled(row, checked)
                return
