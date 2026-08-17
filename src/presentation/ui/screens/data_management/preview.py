from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import create_quick_widget

_QML_DIR = Path(__file__).parent


def build_preview() -> QWidget:
    """Builds a standalone preview for the Data Management screen."""
    quick_widget = create_quick_widget()
    view_model = DataManagementViewModel()
    view_model.status_model.upsert_row(
        "BTCUSDT", "2024-01-01 00:00", "2024-06-01 00:00", "216,000", "OK"
    )
    view_model.status_model.upsert_row(
        "ETHUSDT",
        "2024-01-01 00:00",
        "2024-05-15 08:00",
        "198,400",
        "3 gaps found!",
    )
    view_model.log_model.append("Checking database status for BTCUSDT (1m)...")
    view_model.log_model.append("Scan complete.", level="success")
    view_model.set_stats("414,400", "128.40 MB")
    view_model.useCustomTime = True
    quick_widget.rootContext().setContextProperty("viewModel", view_model)
    quick_widget.resize(1400, 820)
    quick_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / "DatabaseScreen.qml")))
    return quick_widget
