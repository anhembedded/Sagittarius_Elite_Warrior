"""Column spec for the K-line inspector table, and the cell indices
derived from it.

One scope: the indices are `range(len(_KLINE_COLUMNS))`, so a column
added anywhere but here silently renumbers every cell. Shared by the
row widget and the dialog, hence a module rather than a copy in each."""

from __future__ import annotations

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Column,
)

_KLINE_COLUMNS = (
    Column("Thời gian (UTC)", 20),
    Column("Mở (Open)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Cao (High)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Thấp (Low)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Đóng (Close)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Khối lượng (Vol)", 15, Qt.AlignmentFlag.AlignRight),
    Column("Biến động", 11, Qt.AlignmentFlag.AlignRight),
    Column("Số lệnh", 10, Qt.AlignmentFlag.AlignRight),
)
