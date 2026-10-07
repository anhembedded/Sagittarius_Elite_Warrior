"""`trading`'s own slice of `SettingsViewModel` (`EPIC-025E` PR 4.4e).

Carries exactly the fields this module owns: API credentials and the
connection check (`EPIC-034B`: no venue toggles — every venue with a key is on). `market_data`'s venue and sync defaults
moved to `modules/market_data/ui/settings/` instead.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)


class TradingSettingsViewModel(StatusMessageViewModel):
    """@brief State for the Trading settings section."""

    apiKeyChanged = Signal()
    apiSecretChanged = Signal()
    credentialsSourceChanged = Signal()
    connectionCheckChanged = Signal()

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

    @property
    def apiKey(self) -> str:
        return self._api_key

    @apiKey.setter
    def apiKey(self, value: str) -> None:
        if value != self._api_key:
            self._api_key = value
            self.apiKeyChanged.emit()

    @property
    def apiSecret(self) -> str:
        return self._api_secret

    @apiSecret.setter
    def apiSecret(self, value: str) -> None:
        if value != self._api_secret:
            self._api_secret = value
            self.apiSecretChanged.emit()

    @property
    def credentialsSourceLabel(self) -> str:
        return self._credentials_source_label

    @property
    def credentialsLocked(self) -> bool:
        return self._credentials_locked

    @Slot(str, bool)
    def set_credentials_source(self, label: str, locked: bool) -> None:
        """@param label Human-readable name of the source currently in
        effect. @param locked True when an environment variable is what is
        in effect — editing the field here would silently be ignored, so
        the View disables it and shows `label` instead."""
        self._credentials_source_label = label
        self._credentials_locked = locked
        self.credentialsSourceChanged.emit()

    @property
    def connectionChecking(self) -> bool:
        return self._connection_checking

    @property
    def connectionResultText(self) -> str:
        return self._connection_result_text

    @property
    def connectionResultIsError(self) -> bool:
        return self._connection_result_is_error

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

    def load_fields(
        self,
        api_key: str,
        api_secret: str,
    ) -> None:
        self.apiKey = api_key
        self.apiSecret = api_secret
