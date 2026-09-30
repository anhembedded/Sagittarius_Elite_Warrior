"""`trading`'s own slice of `SettingsViewModel` (`EPIC-025E` PR 4.4e).

Carries exactly the fields this module owns: API credentials, which
trading venues are on (`EPIC-028C`: one toggle per venue), and the
connection check. `market_data`'s venue and sync defaults
moved to `modules/market_data/ui/settings/` instead.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Property, Signal, Slot
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)


class TradingSettingsViewModel(StatusMessageViewModel):
    """@brief State for the Trading settings section."""

    apiKeyChanged = Signal()
    apiSecretChanged = Signal()
    credentialsSourceChanged = Signal()
    connectionCheckChanged = Signal()
    venueChanged = Signal()

    #: Emitted when the user clicks Save. The Presenter reads the current
    #: field values off this view model rather than receiving them as
    #: arguments, so adding a field never changes this signal's signature.
    saveRequested = Signal()

    #: `EPIC-021D` — emitted when the user clicks "Check Connection".
    checkConnectionRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._api_key = ""
        self._api_secret = ""
        self._credentials_source_label = ""
        self._credentials_locked = False
        self._connection_checking = False
        self._connection_result_text = ""
        self._connection_result_is_error = False
        self._enabled_venues: tuple[str, ...] = ()
        self._venue_locked = False

    def _get_api_key(self) -> str:
        return self._api_key

    def _set_api_key(self, value: str) -> None:
        if value != self._api_key:
            self._api_key = value
            self.apiKeyChanged.emit()

    apiKey = Property(str, _get_api_key, _set_api_key, notify=apiKeyChanged)

    def _get_api_secret(self) -> str:
        return self._api_secret

    def _set_api_secret(self, value: str) -> None:
        if value != self._api_secret:
            self._api_secret = value
            self.apiSecretChanged.emit()

    apiSecret = Property(str, _get_api_secret, _set_api_secret, notify=apiSecretChanged)

    def _get_credentials_source_label(self) -> str:
        return self._credentials_source_label

    credentialsSourceLabel = Property(
        str, _get_credentials_source_label, notify=credentialsSourceChanged
    )

    def _get_credentials_locked(self) -> bool:
        return self._credentials_locked

    credentialsLocked = Property(
        bool, _get_credentials_locked, notify=credentialsSourceChanged
    )

    @Slot(str, bool)
    def set_credentials_source(self, label: str, locked: bool) -> None:
        """@param label Human-readable name of the source currently in
        effect. @param locked True when an environment variable is what is
        in effect — editing the field here would silently be ignored, so
        the View disables it and shows `label` instead."""
        self._credentials_source_label = label
        self._credentials_locked = locked
        self.credentialsSourceChanged.emit()

    def _get_connection_checking(self) -> bool:
        return self._connection_checking

    connectionChecking = Property(
        bool, _get_connection_checking, notify=connectionCheckChanged
    )

    def _get_connection_result_text(self) -> str:
        return self._connection_result_text

    connectionResultText = Property(
        str, _get_connection_result_text, notify=connectionCheckChanged
    )

    def _get_connection_result_is_error(self) -> bool:
        return self._connection_result_is_error

    connectionResultIsError = Property(
        bool, _get_connection_result_is_error, notify=connectionCheckChanged
    )

    @Slot(bool)
    def set_connection_checking(self, checking: bool) -> None:
        self._connection_checking = checking
        self.connectionCheckChanged.emit()

    @Slot(str, bool)
    def set_connection_result(self, text: str, is_error: bool) -> None:
        self._connection_checking = False
        self._connection_result_text = text
        self._connection_result_is_error = is_error
        self.connectionCheckChanged.emit()

    @Slot()
    def requestCheckConnection(self) -> None:
        self.checkConnectionRequested.emit()

    @Property(list, notify=venueChanged)
    def enabledVenues(self) -> list[str]:
        """The venues switched on, as `TradingVenue` values; empty means
        trading is off."""
        return list(self._enabled_venues)

    @Property(bool, notify=venueChanged)
    def venueLocked(self) -> bool:
        """True while live trading is on — `BOT-125`: changing where orders
        go mid-session would redefine what everything already in flight
        means (`EPIC-022` §4.1, same reasoning)."""
        return self._venue_locked

    @Slot(str, bool)
    def requestVenueEnabled(self, venue: str, enabled: bool) -> None:
        if enabled and venue not in self._enabled_venues:
            self._enabled_venues = (*self._enabled_venues, venue)
        elif not enabled and venue in self._enabled_venues:
            self._enabled_venues = tuple(v for v in self._enabled_venues if v != venue)
        else:
            return
        self.venueChanged.emit()

    def load_fields(
        self,
        api_key: str,
        api_secret: str,
        enabled_venues: Sequence[str],
    ) -> None:
        self._set_api_key(api_key)
        self._set_api_secret(api_secret)
        self._enabled_venues = tuple(enabled_venues)
        self.venueChanged.emit()

    @Slot(bool)
    def set_venue_locked(self, locked: bool) -> None:
        self._venue_locked = locked
        self.venueChanged.emit()

    @Slot()
    def requestSave(self) -> None:
        self.saveRequested.emit()
