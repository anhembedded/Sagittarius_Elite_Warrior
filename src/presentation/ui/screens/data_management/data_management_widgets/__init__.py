"""QtWidgets building blocks for DatabaseScreen (EPIC-005E), each a direct port of
one QML component this screen used: `TimeRangeCard`, `LogPanel`, `AppProgressBar`
(all from the engine kit or `components/`), and the `SymbolPickerModal`/
`ModalDialogCard` confirm-dialog pattern. Kept in their own module so
`data_management_view.py` stays about assembly, not primitive construction.

Split by `EPIC-007G` into one module per widget. This package re-exports
the same names, so no call site changed.
"""

from __future__ import annotations

from .database_status_panel import DatabaseStatusPanel
from .field_style import field_style
from .gap_inspector_dialog import GapInspectorDialog
from .kline_inspector_dialog import KlineInspectorDialogWidget
from .time_range_card import TimeRangeCardWidget

__all__ = [
    "DatabaseStatusPanel",
    "GapInspectorDialog",
    "KlineInspectorDialogWidget",
    "TimeRangeCardWidget",
    "field_style",
]
