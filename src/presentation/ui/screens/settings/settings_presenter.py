from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action

from .settings_view_model import SettingsViewModel

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .settings_view import SettingsView

_SYMBOL_SEPARATOR = ","

_SAVED_MESSAGE = (
    "Đã lưu vào bộ nhớ (chưa ghi xuống user_config.json). "
    "API Key/Secret cần khởi động lại app để có hiệu lực."
)
_EMPTY_SYMBOLS_MESSAGE = "Default Symbols không được để trống."


class SettingsPresenter(BasePresenter):
    """
    @brief Presenter for the API & Credentials screen (QML — BOT-030 Phase 2).

    @details
    Reads current values from IConfig on construction; Save validates and
    writes back via IConfig.set() — **in-memory only**, since IConfig has no
    disk-write path today (a gap first flagged in BOT-028's notes, still out
    of scope here; the screen's warning banner says so plainly rather than
    implying persistence that doesn't exist).

    Business logic lives here rather than in SettingsViewModel, which stays
    a pure QML state bridge — the same split SidebarViewModel uses. No FSM:
    Save is synchronous and instant, with no background work to lock the UI
    against.
    """

    def __init__(self, view: "SettingsView", container: "IContainer") -> None:
        super().__init__(view, container)

        self._settings_view_model = SettingsViewModel()
        view.set_view_model(self._settings_view_model)
        self._load_from_config()

        # Must be called explicitly at the end of __init__ per BasePresenter
        # contract — and before load_qml(), so the QML document parses against
        # a view model that already holds real values.
        self._connect_ui_signals()
        self._connect_engine_events()

        view.load_qml("SettingsScreen.qml")

    def _connect_ui_signals(self) -> None:
        self._settings_view_model.saveRequested.connect(self._on_save)

    def _connect_engine_events(self) -> None:
        """Nothing to subscribe to — Settings has no background/live data."""

    def _load_from_config(self) -> None:
        values = self.config.get_all()
        symbols = values.get("DEFAULT_SYMBOLS") or []
        self._settings_view_model.load_fields(
            api_key=values.get("API_KEY") or "",
            api_secret=values.get("API_SECRET") or "",
            default_symbols=f"{_SYMBOL_SEPARATOR} ".join(symbols),
            default_interval=values.get("DEFAULT_INTERVAL") or "",
            default_sync_days=int(values.get("DEFAULT_SYNC_DAYS") or 1),
        )

    @Slot()
    @safe_ui_action
    def _on_save(self) -> None:
        """
        Validates, then writes every field via IConfig.set(). Symbols are
        checked before any set() call so a rejected save never applies
        partially. Sync days needs no check here — the QML SpinBox's `from: 1`
        already constrains it to a positive value.
        """
        view_model = self._settings_view_model
        symbols = self._parse_symbols(view_model.defaultSymbols)
        if not symbols:
            view_model.set_status(_EMPTY_SYMBOLS_MESSAGE, is_error=True)
            return

        self.config.set("API_KEY", view_model.apiKey)
        self.config.set("API_SECRET", view_model.apiSecret)
        self.config.set("DEFAULT_SYMBOLS", symbols)
        self.config.set("DEFAULT_INTERVAL", view_model.defaultInterval.strip())
        self.config.set("DEFAULT_SYNC_DAYS", view_model.defaultSyncDays)

        view_model.set_status(_SAVED_MESSAGE, is_error=False)

    @staticmethod
    def _parse_symbols(raw: str) -> list[str]:
        return [part.strip() for part in raw.split(_SYMBOL_SEPARATOR) if part.strip()]
