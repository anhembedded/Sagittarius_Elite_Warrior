"""`ChartFrame` — the stock frame every chart sits in (`EPIC-033H`): a title
and the chart's own header controls in one row, the plot below.

`ChartCard` was a `Card` of the old widget kit, which styles itself through
`apply_role()`: a style sheet on every chart, which the workbench
conformance suite refuses (`ui-presentation-rule.md` §1). A chart in a
mode's central widget or a dock needs no card of its own — the tab or the
dock is its frame (§8: no inner card). This keeps the three things charts
used of `Card` — `title`, `header_actions` and `body_layout` — on a plain
`QWidget`, so no caller changes, and lets the style draw the rest.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


class ChartFrame(QWidget):
    """A title row with room for header controls, above `body_layout`."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout = QVBoxLayout(self)
        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        self._title_label = plain_label(title)
        header_row.addWidget(self._title_label)
        header_row.addStretch()
        #: Header-level controls, right-aligned in the order they are added.
        self.header_actions = QHBoxLayout()
        header_row.addLayout(self.header_actions)
        self.body_layout.addWidget(header)

    @property
    def title(self) -> str:
        return self._title_label.text()

    @title.setter
    def title(self, value: str) -> None:
        self._title_label.setText(value)
