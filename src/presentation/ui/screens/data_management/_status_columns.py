"""Column spec for the Data Management status table, the cell indices
derived from it, and the row actions those cells render.

One scope: the indices are `range(len(_STATUS_COLUMNS))`, so a column
added anywhere but beside the spec silently renumbers every cell. The
row widget and the view both read all of this, so it lives in one
module rather than being copied into each."""

from __future__ import annotations

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Column,
)

_STATUS_COLUMNS = (
    Column("SYMBOL", 22),
    Column("TF", 10, Qt.AlignmentFlag.AlignCenter),
    Column("FIRST RECORD", 28),
    Column("LAST RECORD", 28),
    Column("TOTAL", 18),
    Column("STATUS", 22),
)

_ACTIONS_COLUMN = Column("ACTIONS", 26)
