"""What the Backtest read-out tables share (`EPIC-033L`, review of PR #365):
the colour a tone reads, and a `SpecTable` that sorts on `SORT_ROLE`.

The comparison tables (`metric_comparison_model.py`) and Metrics Detail
(`metrics_detail_model.py`) show values that arrive as formatted text in
mixed units, money beside a percentage beside a count, so a header click
cannot sort them as numbers. Their models serve a sort key under
`SORT_ROLE`, and `readout_table()` points the table's proxy at it. A tone is
coloured from `semantic_colour`, the app's one table of meanings
(`ui-presentation-rule.md` §1), beside the sign or words that say the same.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone, semantic_colour
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel

#: What a read-out table sorts on, in place of the formatted text.
SORT_ROLE = Qt.ItemDataRole.UserRole + 1
_TONE_COLOURS = {Tone.POSITIVE: "success", Tone.NEGATIVE: "danger"}


def tone_colour(tone: Tone) -> QColor | None:
    """A tone's colour, or `None` for no verdict: the platform's text colour."""
    name = _TONE_COLOURS.get(tone)
    return QColor(semantic_colour(name)) if name is not None else None


def readout_table[TRow](
    model: RowTableModel[TRow], object_name: str, empty_text: str
) -> SpecTable[TRow]:
    """A read-out's table, sorting on `SORT_ROLE`."""
    table = SpecTable(model, object_name=object_name, empty_text=empty_text)
    table.proxy.setSortRole(SORT_ROLE)
    return table
