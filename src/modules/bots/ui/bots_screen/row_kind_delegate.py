"""`BOT-206` — a property table's value is aligned by the kind of its row, not of its column.

The Engine's `KindDelegate` aligns every cell of a column by the column's kind, which suits a table
whose column holds one kind of value. A property sheet's Value column holds a symbol, a price, a
verdict and a duration in turn, and the owner asked that text read left and a number right
(2026-10-20), as a Windows property sheet does. A cell says its kind in `ROW_KIND_ROLE`; this
delegate is the Engine's, writing the text as the Engine does, with the alignment of that kind (and,
since `EPIC-043C`, the colour of the tone a cell names). A cell that names none keeps its column's.

Extension cases: a row of another kind is one `ColumnKind` on its `PropertyRow`; a second column
that mixes kinds is one more column index here.
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QStyleOptionViewItem
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_delegate import ToneKindDelegate
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: The item data role a cell answers with the `ColumnKind` of its row (an `int` of `UserRole`).
ROW_KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class RowKindDelegate(ToneKindDelegate):
    """The Engine's delegate, aligning a cell by the kind its row names and painting it in its
    tone (`ToneKindDelegate`)."""

    @override
    def initStyleOption(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        super().initStyleOption(option, index)
        kind = index.data(ROW_KIND_ROLE)
        if isinstance(kind, ColumnKind):
            option.displayAlignment = kind.alignment  # type: ignore[attr-defined]
