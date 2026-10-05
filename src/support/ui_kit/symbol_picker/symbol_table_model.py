"""The picker's rows, as a model — `EPIC-025` PR 4.3a.

## Why a model, and why this replaces a grid of cards

`SymbolPickerOverlay` used to build one `SymbolCard` widget per entry into two
`QGridLayout`s inside a `QScrollArea`. With fourteen hundred pairs that is
fourteen hundred widgets constructed on every keystroke, and it froze — which is
why `presentation/ui/qml/SymbolPicker/` exists at all: its own docstring says it
replaces this dialog *"eliminating UI freeze when displaying thousands of
symbols via virtualized QML GridView"*. So the app carried **two** symbol
pickers, one per toolkit, and ADR D21 deletes the QML one.

A `QTableView` on a model virtualises natively: it asks `data()` only for the
rows it is about to paint. That is the same virtualisation the QML `GridView`
was brought in for, from the toolkit the app is keeping — ADR D20's "no
hand-drawn substitute for a component the platform already has", and HLD §11.3's
table row: *"a table (`QTableView` on a model)"*.

It also retires the card, which is a decision already taken rather than one made
here: HLD §11.3 retires `kit.Card` outright on the user's own judgement
(*"các card cũ cũng rất là tệ"*), and `SymbolCard` was a `SelectableCard`.

## The three columns, and what each is for

`SYMBOL` carries the pair, `STATUS` says why this row might matter (it is the
current one, or a recent one, or which asset it quotes in), and `FAVOURITE`
carries the star. The star is a **column** rather than a painted hit-rect inside
one cell because a column is what the platform gives for free: `QTableView`
reports the clicked index, so "did the user click the star or the row" is a
column comparison rather than mouse arithmetic against a delegate's geometry.

The order is the picker's own — favourites first, then everything else, both
in the order the filter produced — and that order is information
(`partition_favourites`). The overlay shows the table through
`configure_item_view` like every other (`EPIC-033N`), but it hides the header,
so no click re-sorts it and the proxy keeps the model's order.
"""

from __future__ import annotations

from typing import ClassVar, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

from .filtering import SymbolEntry

#: Shown in `STATUS` instead of the quote asset when this is the symbol the
#: screen is already running on — the state a user scanning the list most needs
#: to find, and the one thing worth spending the column on.
_CURRENT_TEXT = "Current"
_RECENT_TEXT = "Recent"
_QUOTE_TEXT = "Quote {quote}"
_UNKNOWN_QUOTE_TEXT = "—"

_STAR_ON = "★"
_STAR_OFF = "☆"

_ADD_FAVOURITE_TOOLTIP = "Add to favourites"
_REMOVE_FAVOURITE_TOOLTIP = "Remove from favourites"


class SymbolTableModel(RowTableModel[SymbolEntry]):
    """Every symbol the current filter admits, favourites first."""

    SYMBOL_COLUMN: Final = 0
    STATUS_COLUMN: Final = 1
    FAVOURITE_COLUMN: Final = 2

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("status", "Status", ColumnKind.STATUS),
        ColumnSpec("favourite", "Favourite", ColumnKind.TEXT),
    )

    def _value(self, row: SymbolEntry, column: int) -> DisplayValue:
        if column == self.SYMBOL_COLUMN:
            return row.symbol
        if column == self.STATUS_COLUMN:
            return self._status_text(row)
        return _STAR_ON if row.is_favourite else _STAR_OFF

    def _role_data(self, row: SymbolEntry, column: int, role: int) -> object:
        if column == self.FAVOURITE_COLUMN and role == Qt.ItemDataRole.ToolTipRole:
            return (
                _REMOVE_FAVOURITE_TOOLTIP
                if row.is_favourite
                else _ADD_FAVOURITE_TOOLTIP
            )
        if (
            role == Qt.ItemDataRole.FontRole
            and column == self.SYMBOL_COLUMN
            and row.is_current
        ):
            # The row the screen is already running on, in bold. It replaces
            # the card's "selected" border and is the only emphasis this table
            # carries — ADR D21 leaves colour to the OS palette, and Qt has no
            # palette role meaning "this is the one you are on".
            font = QFont()
            font.setBold(True)
            return font
        return None

    @staticmethod
    def _status_text(row: SymbolEntry) -> str:
        if row.is_current:
            return _CURRENT_TEXT
        if row.is_recent:
            return _RECENT_TEXT
        if row.parts.has_known_quote:
            return _QUOTE_TEXT.format(quote=row.parts.quote)
        return _UNKNOWN_QUOTE_TEXT
