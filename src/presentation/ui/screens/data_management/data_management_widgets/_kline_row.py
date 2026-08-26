"""One row of the K-line inspector table, and the model-class resolver.

`_kline_model_class` sits here rather than with the dialog because the
row widget is its only caller. Putting it with the dialog made the two
modules import each other -- the dialog builds rows, the rows needed
the resolver. Redrawing the boundary is the fix `EPIC-007G` asks for;
a function-local import to break the cycle is banned by code-rule.md."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    DataRow,
    StyleRole,
    Tone,
)

from ._kline_columns import _KLINE_COLUMNS

if TYPE_CHECKING:
    from ..kline_inspector_table_model import KLineInspectorTableModel


(
    _TIME_CELL,
    _OPEN_CELL,
    _HIGH_CELL,
    _LOW_CELL,
    _CLOSE_CELL,
    _VOLUME_CELL,
    _CHANGE_CELL,
    _TRADES_CELL,
) = range(len(_KLINE_COLUMNS))


def _kline_model_class(model) -> type[KLineInspectorTableModel]:
    """`index.model()` is the real `KLineInspectorTableModel` here (no proxy,
    unlike the status table) — this just gives the role constants a typed
    name to read at the call site."""
    return type(model)


class _KLineRowWidget(DataRow):
    """One row of the KLine table, on the engine's `DataRow`.

    Same `setIndexWidget` pattern as `_StatusRowWidget`, for the same
    reason: `KLineInspectorTableModel` addresses its fields by role
    (`data(index, role)`) rather than by `index.column()`, even though
    `columnCount()` returns 11 — it was built for a QML delegate reading
    named roles per row, not for a real per-column `QTableView`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_KLINE_COLUMNS, parent=parent)
        self.setFixedHeight(28)
        self.layout().setContentsMargins(8, 0, 8, 0)
        self.layout().setSpacing(4)

        # Monospace on every cell — a column of prices only lines up if its
        # digits are the same width. A font is a widget API call, not a
        # styling decision, which is why `DataRow.cell()` is reachable.
        for position in range(len(_KLINE_COLUMNS)):
            font = self.cell(position).font()
            font.setFamily("monospace")
            self.cell(position).setFont(font)

        # Volume and trade count recede: they are context for the four price
        # columns, not the figures a user is reading the row for.
        self.set_cell_role(_VOLUME_CELL, StyleRole.CAPTION)
        self.set_cell_role(_TRADES_CELL, StyleRole.CAPTION)
        self.set_cell_role(_CLOSE_CELL, StyleRole.TABLE_CELL_STRONG)

    def apply_row(self, index: QModelIndex, row_number: int) -> None:
        model = index.model()
        model_roles = _kline_model_class(model)
        is_bullish = bool(model.data(index, model_roles.IsBullishRole))
        tone = Tone.POSITIVE if is_bullish else Tone.NEGATIVE

        # Zebra striping, scoped to this class so it cannot cascade into the
        # cells — the unscoped form is a bare property list, which is Qt's
        # universal selector and overrides a child's own colour (`BUG-008`).
        stripe = Palette.BG_CARD if row_number % 2 == 0 else Palette.BG
        self.setStyleSheet(f"{type(self).__name__} {{ background-color: {stripe}; }}")

        self.set_cells(
            [
                str(model.data(index, model_roles.FormattedTimeRole) or ""),
                str(model.data(index, model_roles.OpenRole) or "0"),
                str(model.data(index, model_roles.HighRole) or "0"),
                str(model.data(index, model_roles.LowRole) or "0"),
                str(model.data(index, model_roles.CloseRole) or "0"),
                str(model.data(index, model_roles.VolumeRole) or "0"),
                str(model.data(index, model_roles.ChangePctRole) or "0.00%"),
                str(model.data(index, model_roles.TradesRole) or 0),
            ]
        )
        self.set_cell_role(_CLOSE_CELL, StyleRole.TABLE_CELL_STRONG)
        self.set_cell_tone(_CLOSE_CELL, tone)
        self.set_cell_role(_CHANGE_CELL, StyleRole.TABLE_CELL)
        self.set_cell_tone(_CHANGE_CELL, tone)
