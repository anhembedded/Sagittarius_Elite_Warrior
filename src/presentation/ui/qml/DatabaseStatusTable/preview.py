"""Standalone live preview for the DatabaseStatusTable QML component.

Seeds the real `DatabaseStatusTableModel` via its own `upsert_row()` — the
same two example shards the mockup shows — rather than fabricating a
second data shape (see NOTES.md).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_table_model import (
    DatabaseStatusTableModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_vm import (
    DatabaseStatusVM,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML_FILE = Path(__file__).with_name("DatabaseStatusTable.qml")


def build_preview() -> QWidget:
    """Builds the table body with two example shards, no host chrome."""
    model = DatabaseStatusTableModel()
    model.upsert_row(
        symbol="BTCUSDT",
        first_record="2026-07-23 15:41:05",
        last_record="2026-08-26 01:19:21",
        total_candles="2,885,897",
        status_text="OK",
        interval="1s",
    )
    model.upsert_row(
        symbol="BTCUSDT",
        first_record="2026-07-27 07:30:00",
        last_record="2026-08-26 07:00:00",
        total_candles="1,440",
        status_text="OK",
        interval="30m",
    )
    vm = DatabaseStatusVM(model)

    quick = QQuickWidget()
    quick.setObjectName("databaseStatusTablePreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", get_theme_bridge())
    # QML context properties are borrowed references; retain both for the
    # scene lifetime, same reasoning `QmlOverlay.__init__` documents.
    quick._database_status_vm = vm
    quick._database_status_model = model

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )
    quick.resize(900, 260)
    return quick
