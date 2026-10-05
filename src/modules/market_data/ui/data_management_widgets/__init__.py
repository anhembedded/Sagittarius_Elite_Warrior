"""The Data mode's widgets (`EPIC-033J`), one module per widget: the coverage
table (`DatabaseStatusPanel`), the Gaps panel, the candle inspector and the
two shard dialogs. Re-exported here so the view imports one package.
"""

from __future__ import annotations

from .database_status_panel import DatabaseStatusPanel
from .gaps_panel import GapsPanel
from .kline_inspector_dialog import KlineInspectorDialog
from .shard_dialogs import ImportDataDialog, SyncHistoryDialog

__all__ = [
    "DatabaseStatusPanel",
    "GapsPanel",
    "ImportDataDialog",
    "KlineInspectorDialog",
    "SyncHistoryDialog",
]
