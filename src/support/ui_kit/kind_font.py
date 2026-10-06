"""`kind_font` — the font a column's kind is written in (`EPIC-033N`,
decision D6 of `DECISION_2026-10-04_windows_workbench.md`).

The application font is the platform's (MS `vis-fonts`); only where digits
must line up down a column — a price, a quantity, an amount of money — is a
value written in the platform's own fixed-pitch font,
`QFontDatabase.systemFont(FixedFont)`, so 1,111.10 and 8,888.80 stand digit
over digit. A percent, a duration, a time and words keep the application
font. The family is never named here: the platform chooses it.

The kind alone decides, never a view: `RowTableModel` answers every cell's
`FontRole` from this, and a model can only add its one emphasis (bold) on
top. The Engine's `KindDelegate` would be the other home for it, beside the
alignment it takes from the kind; it writes the formatter's text only, so
the application's one table model carries it, and every table is one.

Extension cases: another kind whose digits align (a count of trades) is one
member of `DIGIT_ALIGNED_KINDS`; a read-out's values in the same font would
ask the Engine's `ReadoutForm` for a per-kind font, which it does not take.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtGui import QFont, QFontDatabase
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: The kinds whose digits align down a column (D6).
DIGIT_ALIGNED_KINDS: Final = frozenset(
    {ColumnKind.PRICE, ColumnKind.QUANTITY, ColumnKind.MONEY}
)


def kind_font(kind: ColumnKind) -> QFont | None:
    """The platform's fixed-pitch font for a kind whose digits align; `None`
    for every other kind, which keeps the view's own (the application) font."""
    if kind not in DIGIT_ALIGNED_KINDS:
        return None
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
