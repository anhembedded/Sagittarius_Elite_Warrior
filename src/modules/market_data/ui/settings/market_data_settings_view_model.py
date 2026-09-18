"""`market_data`'s own slice of `SettingsViewModel` (`EPIC-025E` PR 4.4e).

Carries exactly the fields this module owns: which venue its candles come
from, and the three per-symbol defaults every screen that syncs history
reads. The Trading venue, credentials and connection check moved to
`modules/trading/ui/settings/` instead — two contributed sections, not one
screen that knew both.
"""

from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)


class MarketDataSettingsViewModel(StatusMessageViewModel):
    """@brief State for the Market Data settings section."""

    defaultSymbolsChanged = Signal()
    defaultIntervalChanged = Signal()
    defaultSyncDaysChanged = Signal()
    venueChanged = Signal()

    #: Emitted when the user clicks Save. The Presenter reads the current
    #: field values off this view model rather than receiving them as
    #: arguments, so adding a field never changes this signal's signature.
    saveRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._default_symbols = ""
        self._default_interval = ""
        self._default_sync_days = 1
        self._market_data_venue = ""

    def _get_default_symbols(self) -> str:
        return self._default_symbols

    def _set_default_symbols(self, value: str) -> None:
        if value != self._default_symbols:
            self._default_symbols = value
            self.defaultSymbolsChanged.emit()

    defaultSymbols = Property(
        str, _get_default_symbols, _set_default_symbols, notify=defaultSymbolsChanged
    )

    def _get_default_interval(self) -> str:
        return self._default_interval

    def _set_default_interval(self, value: str) -> None:
        if value != self._default_interval:
            self._default_interval = value
            self.defaultIntervalChanged.emit()

    defaultInterval = Property(
        str, _get_default_interval, _set_default_interval, notify=defaultIntervalChanged
    )

    def _get_default_sync_days(self) -> int:
        return self._default_sync_days

    def _set_default_sync_days(self, value: int) -> None:
        if value != self._default_sync_days:
            self._default_sync_days = value
            self.defaultSyncDaysChanged.emit()

    defaultSyncDays = Property(
        int,
        _get_default_sync_days,
        _set_default_sync_days,
        notify=defaultSyncDaysChanged,
    )

    @Property(str, notify=venueChanged)
    def marketDataVenue(self) -> str:
        return self._market_data_venue

    @Slot(str)
    def requestMarketDataVenue(self, venue: str) -> None:
        if venue and venue != self._market_data_venue:
            self._market_data_venue = venue
            self.venueChanged.emit()

    def load_fields(
        self,
        default_symbols: str,
        default_interval: str,
        default_sync_days: int,
        market_data_venue: str,
    ) -> None:
        self._set_default_symbols(default_symbols)
        self._set_default_interval(default_interval)
        self._set_default_sync_days(default_sync_days)
        self._market_data_venue = market_data_venue
        self.venueChanged.emit()

    @Slot()
    def requestSave(self) -> None:
        self.saveRequested.emit()
