"""
@brief The concrete `Surface` shapes this package ships — one file per
class, per EPIC-007 §3.4.

@details
Each was extracted from shapes the reference consumer had rewritten two to
five times; each names the real instances it replaces in its own docstring,
and each records what it deliberately left behind. They live here rather
than in `surface.py` because that file holds the family's roots
(`Surface`/`Panel`/`Card`/`SelectableCard`) and is one of
`guards._BASE_DEFINITION_FILES`, which the bare-Qt-base guard skips whole —
a concrete widget parked there would be exempt from the guard purely
because of its address.

`Column` is defined in `data_row` and re-exported here: a row's cells and
the heading strip above them describe the same columns, and the consumer's
one place that keeps those as two separate lists has already let them
drift apart.
"""

from __future__ import annotations

from .banner import Banner, Severity
from .data_row import Column, DataRow, RowAction
from .log_panel import LogModel, LogPanel
from .stat_card import StatCard
from .tab_bar import Tab, TabBar
from .table_card import Pagination, TableCard

__all__ = [
    "Banner",
    "Column",
    "DataRow",
    "LogModel",
    "LogPanel",
    "Pagination",
    "RowAction",
    "Severity",
    "StatCard",
    "Tab",
    "TabBar",
    "TableCard",
]
