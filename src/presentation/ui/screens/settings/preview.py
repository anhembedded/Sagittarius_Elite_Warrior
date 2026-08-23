from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view_model import (
    SettingsViewModel,
)


def build_preview() -> QWidget:
    """Builds a standalone preview for the Settings screen (EPIC-005D — QtWidgets)."""
    view_model = SettingsViewModel()
    view_model.apiKey = "AbCdEf1234567890GhIjKl"
    view_model.apiSecret = "s3cr3t-do-not-share"
    view_model.defaultSymbols = "BTCUSDT, ETHUSDT"
    view_model.defaultInterval = "1m"
    view_model.defaultSyncDays = 30

    view = SettingsView()
    view.set_view_model(view_model)
    view.resize(760, 520)
    return view
