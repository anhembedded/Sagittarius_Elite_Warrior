from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import create_quick_widget

_QML_DIR = Path(__file__).parent


def build_preview() -> QWidget:
    """Builds a standalone preview for the Dev Board panel."""
    quick_widget = create_quick_widget()
    view_model = DashboardQmlViewModel()
    view_model.set_price_ticker("ETHUSDT  3,241.55", "#26a69a")
    view_model.set_ws_status("WS: LIVE", "#26a69a")
    view_model.log_model.append("Prepared 1 charts.")
    view_model.log_model.append(
        "Live stream for ['ETHUSDT'] is running.", level="success"
    )
    view_model.rsiEnabled = True
    quick_widget.rootContext().setContextProperty("viewModel", view_model)
    quick_widget.resize(420, 760)
    quick_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / "DevBoardPanel.qml")))
    return quick_widget
