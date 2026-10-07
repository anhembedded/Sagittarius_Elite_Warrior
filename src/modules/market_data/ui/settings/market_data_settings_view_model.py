"""`market_data`'s own slice of `SettingsViewModel` (`EPIC-025E` PR 4.4e).

Carries exactly the fields this module owns: the three per-symbol defaults
every screen that syncs history reads. The Trading venue, credentials and connection check moved to
`modules/trading/ui/settings/` instead — two contributed sections, not one
screen that knew both.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)


class MarketDataSettingsViewModel(StatusMessageViewModel):
    """@brief State for the Market Data settings section."""

    defaultSymbolsChanged = Signal()
    defaultIntervalChanged = Signal()
    defaultSyncDaysChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._default_symbols = ""
        self._default_interval = ""
        self._default_sync_days = 1

    @property
    def defaultSymbols(self) -> str:
        return self._default_symbols

    @defaultSymbols.setter
    def defaultSymbols(self, value: str) -> None:
        if value != self._default_symbols:
            self._default_symbols = value
            self.defaultSymbolsChanged.emit()

    @property
    def defaultInterval(self) -> str:
        return self._default_interval

    @defaultInterval.setter
    def defaultInterval(self, value: str) -> None:
        if value != self._default_interval:
            self._default_interval = value
            self.defaultIntervalChanged.emit()

    @property
    def defaultSyncDays(self) -> int:
        return self._default_sync_days

    @defaultSyncDays.setter
    def defaultSyncDays(self, value: int) -> None:
        if value != self._default_sync_days:
            self._default_sync_days = value
            self.defaultSyncDaysChanged.emit()

    def load_fields(
        self,
        default_symbols: str,
        default_interval: str,
        default_sync_days: int,
    ) -> None:
        self.defaultSymbols = default_symbols
        self.defaultInterval = default_interval
        self.defaultSyncDays = default_sync_days
