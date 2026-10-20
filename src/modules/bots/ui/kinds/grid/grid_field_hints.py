"""`EPIC-034F`, `BOT-209` — what a Grid's fields say about themselves: the line under each.

Each editable field sits above a sign and one line (`FieldError.text`, the check's own
`summary`), empty and hidden until a verdict is about that field; the whole sentence is the
field's tooltip. The Grids field may also carry a button, "Use 36 grids", when the check names a
count that clears it. The words come from `field_errors`; this class only lays them out.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_display import (
    marker_icon,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_errors import (
    GRID_COUNT,
    FieldError,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

#: Binance's own floor for a Spot grid; the planner refuses fewer anyway.
MIN_GRIDS = 2
MAX_GRIDS = 1000


class FieldHints:
    """@brief The sign, the line and, for the Grids field, the button under each field."""

    def __init__(self, owner: QWidget) -> None:
        self._owner = owner
        self.use_suggested_grids = QPushButton()
        self.use_suggested_grids.setObjectName("btnGridUseSuggested")
        self.use_suggested_grids.setVisible(False)
        self._suggested = 0
        self._error_labels: dict[str, QLabel] = {}
        self._marker_labels: dict[str, QLabel] = {}

    def under(self, key: str, editor: QWidget) -> QWidget:
        """The editor with, under it, what the constraints say about it."""
        error = plain_label()
        error.setObjectName(f"lblGridError_{key}")
        error.setWordWrap(True)
        error.setVisible(False)
        self._error_labels[key] = error
        marker = plain_label()
        marker.setObjectName(f"lblGridMarker_{key}")
        marker.setVisible(False)
        self._marker_labels[key] = marker
        said = QHBoxLayout()
        said.setContentsMargins(0, 0, 0, 0)
        said.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
        said.addWidget(error, 1)
        if key == GRID_COUNT:
            said.addWidget(self.use_suggested_grids, 0, Qt.AlignmentFlag.AlignTop)
        row = QWidget()
        column = QVBoxLayout(row)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(editor)
        column.addLayout(said)
        return row

    def fields(self) -> tuple[str, ...]:
        return tuple(self._error_labels)

    def show(self, shown: Mapping[str, FieldError]) -> None:
        for key, label in self._error_labels.items():
            error = shown.get(key)
            label.setText(error.text if error else "")
            label.setVisible(error is not None)
            self._mark(key, error)

    def text_of(self, key: str) -> str:
        """What a field says now, `""` when nothing is about it."""
        label = self._error_labels[key]
        return label.text() if not label.isHidden() else ""

    def offer_grid_count(
        self, error: FieldError | None, current: int, enabled: bool
    ) -> None:
        """ "Use 36 grids" when the Grids hint names a count other than the one the field shows."""
        count = error.use_grids if error else 0
        self._suggested = count
        offered = MIN_GRIDS <= count <= MAX_GRIDS and count != current
        button = self.use_suggested_grids
        button.setVisible(offered)
        button.setEnabled(enabled)
        if offered:
            button.setText(f"Use {count} grids")

    def marker_of(self, key: str) -> QLabel:
        """The sign beside a field's line."""
        return self._marker_labels[key]

    @property
    def suggested_grids(self) -> int:
        return self._suggested

    def _mark(self, key: str, error: FieldError | None) -> None:
        """A sign beside the sentence, from the platform's own icons: a stop sign
        for what blocks Start, information for advice, and its words for a screen
        reader. Colour is never the only signal."""
        marker = self._marker_labels[key]
        marker.setVisible(error is not None)
        if error is None:
            marker.clear()
            marker.setAccessibleName("")
            return
        icon = marker_icon(error.blocks)
        size = marker.fontMetrics().height()
        marker.setPixmap(
            self._owner.style()
            .standardIcon(icon)
            .pixmap(QSize(size, size), marker.devicePixelRatioF())
        )
        marker.setAccessibleName("Blocks Start" if error.blocks else "Advice")
