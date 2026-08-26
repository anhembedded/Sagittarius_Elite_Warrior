from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.state.container_lookup import (
    find_state_coordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

from .settings_view_model import SettingsViewModel

#: `EPIC-010H` — which remembered keys each screen loses when this screen
#: saves. Only the values `DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` actually
#: govern; everything else those slices hold (leverage, commission, the
#: script checklist, the lookback window) is none of Settings' business.
#:
#: The Dev Board and Database screens joined this map in the same change that
#: made them read those config keys at all. Before that they ignored Settings
#: entirely, so Settings outranked nothing of theirs and invalidating their
#: remembered values would have been wrong — it would have discarded a real
#: user choice in favour of a default that screen never consulted.
_STATE_KEYS_OWNED_BY_SETTINGS: dict[str, tuple[str, ...]] = {
    "backtest": ("symbol", "timeframe"),
    "dashboard": ("symbol", "interval"),
    "data_management": ("symbol", "interval"),
}

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .settings_view import SettingsView

_SYMBOL_SEPARATOR = ","

_SAVED_MESSAGE = (
    "Đã lưu vào user_config.json. API Key/Secret cần khởi động lại app để có hiệu lực."
)
_SAVED_IN_MEMORY_ONLY_MESSAGE = (
    "Đã áp dụng cho phiên chạy hiện tại, nhưng KHÔNG ghi được xuống "
    "user_config.json — thay đổi sẽ mất khi khởi động lại app."
)
_EMPTY_SYMBOLS_MESSAGE = "Default Symbols không được để trống."


class SettingsPresenter(BasePresenter):
    """
    @brief Presenter for the API & Credentials screen (QML — BOT-030 Phase 2).

    @details
    Reads current values from IConfig on construction; Save validates, writes
    back via IConfig.set(), then persists to disk via ConfigManager.save()
    (the disk-write path first flagged as missing in BOT-028's notes, now
    added at the engine level). The isinstance check exists because save()
    is a ConfigManager-specific capability, not part of the IConfig port —
    a DictConfig or other IConfig implementation swapped in for tests simply
    won't persist, which is the correct behaviour for those.

    save() failure (e.g. no writable source configured, or a real disk
    error) is caught here rather than left to `safe_ui_action`'s outer
    swallow — that swallow would otherwise skip `set_status()` entirely,
    leaving the user staring at a blank status line with no idea whether
    Save did anything at all.

    Business logic lives here rather than in SettingsViewModel, which stays
    a pure QML state bridge — the same split SidebarViewModel uses. No FSM:
    Save is synchronous and instant, with no background work to lock the UI
    against.
    """

    def __init__(self, view: SettingsView, container: IContainer) -> None:
        super().__init__(view, container)

        self._settings_view_model = SettingsViewModel()
        self._load_from_config()

        # EPIC-010H — this screen owns DEFAULT_SYMBOLS/DEFAULT_INTERVAL, so
        # saving them has to invalidate the remembered values that outrank
        # them (see `_discard_outranked_state`).
        self._state_coordinator: UiStateCoordinator | None = find_state_coordinator(
            container
        )

        # view.set_view_model() now happens AFTER _load_from_config() (order
        # flipped from the QML version, EPIC-005D): SettingsView reads the
        # view model's field values immediately, synchronously, to populate
        # its QLineEdit/QSpinBox widgets — unlike QmlHostView.set_view_model(),
        # which only registered a context property for QML to bind against
        # later at load_qml() time, so the old order (before load) was
        # correct for QML and would show blank fields here.
        self._connect_ui_signals()
        self._connect_engine_events()

        view.set_view_model(self._settings_view_model)

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

        if isinstance(self.config, ConfigManager):
            try:
                self.config.save()
            except (ValueError, OSError) as exc:
                self.logger.error(f"SettingsPresenter: config save failed: {exc}")
                view_model.set_status(_SAVED_IN_MEMORY_ONLY_MESSAGE, is_error=True)
                return

        self._discard_outranked_state()
        view_model.set_status(_SAVED_MESSAGE, is_error=False)

    def _discard_outranked_state(self) -> None:
        """Forgets the remembered values this save has just overruled.

        @details `EPIC-010H` settles the three-tier order as

            ui_state  >  user_config DEFAULT_*  >  module constants

        which has one mandatory consequence: a remembered value outranks the
        Settings default, so changing that default must drop the remembered
        one. Without this, the user edits Settings, presses Save, and nothing
        appears to happen — the older, higher-priority value keeps winning.

        Scoped to the two keys this screen actually owns. Dropping whole
        slices instead would take every unrelated remembered value on those
        screens (leverage, commission, timezone, the script checklist) with
        it, which is worse than the problem being fixed — and is why
        `IStateStore` grew `discard_keys()` for this.

        Unconditional rather than compared against the previous value: Save
        is an explicit act, and "make sure this is not remembered" is
        idempotent, so re-saving an unchanged field costs one harmless write
        and needs no before/after bookkeeping to stay correct.
        """
        if self._state_coordinator is None:
            return
        for scope_key, keys in _STATE_KEYS_OWNED_BY_SETTINGS.items():
            self._state_coordinator.discard_keys(StateScope(key=scope_key), keys)

    @staticmethod
    def _parse_symbols(raw: str) -> list[str]:
        return [part.strip() for part in raw.split(_SYMBOL_SEPARATOR) if part.strip()]
