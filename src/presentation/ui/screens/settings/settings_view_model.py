from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel


class SettingsViewModel(BaseQmlViewModel):
    """
    @brief QML-facing state for the API & Credentials screen.

    @details
    Deliberately holds NO business logic: it carries the editable field
    values and the status line, and turns a Save click into a
    `saveRequested` signal for SettingsPresenter to act on. Validation and
    IConfig access stay in the Presenter — the same split used by
    SidebarViewModel (which emits `navigationRequested` rather than routing
    itself), so "what the UI shows" and "what the app does about it" don't
    get tangled together.

    Field properties are read/write so QML can bind two-way (`text:` reads,
    `onTextEdited:` writes); the status pair is written only from Python.
    """

    apiKeyChanged = Signal()
    apiSecretChanged = Signal()
    defaultSymbolsChanged = Signal()
    defaultIntervalChanged = Signal()
    defaultSyncDaysChanged = Signal()
    statusChanged = Signal()

    #: Emitted when the user clicks Save. The Presenter reads the current
    #: field values off this view model rather than receiving them as
    #: arguments, so adding a field never changes this signal's signature.
    saveRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._api_key = ""
        self._api_secret = ""
        self._default_symbols = ""
        self._default_interval = ""
        self._default_sync_days = 1
        self._status_message = ""
        self._status_is_error = False

    # ------------------------------------------------------------------ #
    # Editable fields (two-way bound from QML)
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Status line (written from Python only)
    # ------------------------------------------------------------------ #

    def _get_status_message(self) -> str:
        return self._status_message

    statusMessage = Property(str, _get_status_message, notify=statusChanged)

    def _get_status_is_error(self) -> bool:
        return self._status_is_error

    statusIsError = Property(bool, _get_status_is_error, notify=statusChanged)

    @Slot(str, bool)
    def set_status(self, message: str, is_error: bool) -> None:
        self._status_message = message
        self._status_is_error = is_error
        self.statusChanged.emit()

    # ------------------------------------------------------------------ #
    # Bulk load (from IConfig, via the Presenter)
    # ------------------------------------------------------------------ #

    def load_fields(
        self,
        api_key: str,
        api_secret: str,
        default_symbols: str,
        default_interval: str,
        default_sync_days: int,
    ) -> None:
        """Populates every field at once; each setter emits its own change
        signal so QML bindings refresh."""
        self._set_api_key(api_key)
        self._set_api_secret(api_secret)
        self._set_default_symbols(default_symbols)
        self._set_default_interval(default_interval)
        self._set_default_sync_days(default_sync_days)

    @Slot()
    def requestSave(self) -> None:
        """Called from QML's Save button."""
        self.saveRequested.emit()
