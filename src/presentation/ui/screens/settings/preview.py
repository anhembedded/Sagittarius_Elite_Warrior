from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view_model import (
    SettingsViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import create_quick_widget

_QML_DIR = Path(__file__).parent


def build_preview() -> QWidget:
    """Builds a standalone preview for the Settings screen."""
    quick_widget = create_quick_widget()
    view_model = SettingsViewModel()
    view_model.apiKey = "AbCdEf1234567890GhIjKl"
    view_model.apiSecret = "s3cr3t-do-not-share"
    view_model.defaultSymbols = "BTCUSDT, ETHUSDT"
    view_model.defaultInterval = "1m"
    view_model.defaultSyncDays = 30
    quick_widget.rootContext().setContextProperty("viewModel", view_model)
    quick_widget.resize(760, 520)
    quick_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / "SettingsScreen.qml")))
    return quick_widget
