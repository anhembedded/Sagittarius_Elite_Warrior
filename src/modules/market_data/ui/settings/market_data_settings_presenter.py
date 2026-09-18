"""`market_data`'s own settings section: venue + sync defaults (`EPIC-025E` PR 4.4e).

Split off the old monolithic `SettingsPresenter` — this Presenter owns
exactly the config keys `market_data` reads elsewhere in its own module
(`DEFAULT_SYMBOLS`, `DEFAULT_INTERVAL`, `DEFAULT_SYNC_DAYS`,
`EXCHANGE_MARKET_DATA_VENUE`), and nothing that belongs to `trading`.

**Finding, not a regression:** the old monolith disabled this venue's combo
too while trading was active, under one shared "venues locked" flag it read
from `ITradingSession`. That flag cannot follow this field into `market_data`
— `trading.dependencies` already names `["market_data"]`
(`modules/trading/module.py`), so `market_data` reading `ITradingSession`
back would be the exact import cycle `ExtensionCircularDependencyError`
caught on PR 4.4c's first attempt (`DECISION_2026-09-17_strategy_ui_
contributes_rather_than_being_imported.md` §8). Unlike the Order venue, this
one only ever selects which venue's candles a chart reads; the original
lock's own reasoning ("saving mid-session would leave a config on disk that
contradicts the session still running") is a UX consistency nicety, not an
order-routing safety rule, so it is dropped here rather than solved with a
new cross-module port for a lock this field never needed as urgently as
Trading's own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_market_data_venue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL_OPTIONS,
    default_interval,
    default_symbol_options,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.container_lookup import (
    find_state_coordinator,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

from .market_data_settings_view_model import MarketDataSettingsViewModel

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .market_data_settings_view import MarketDataSettingsView

_SYMBOL_SEPARATOR = ","

_SAVED_MESSAGE = (
    "Saved to user_config.json. Data Source requires an app restart to take effect."
)
_SAVED_IN_MEMORY_ONLY_MESSAGE = (
    "Applied to the current session, but could NOT be written to "
    "user_config.json — the change will be lost on the next app restart."
)
_EMPTY_SYMBOLS_MESSAGE = "Default Symbols must not be empty."

#: `EPIC-010H`'s precedence rule (`ui_state > user_config DEFAULT_*`) means
#: saving one of these two config keys must invalidate whatever remembered
#: value now outranks it (`EPIC-017A`).
_CONFIG_KEYS_THAT_OUTRANK_REMEMBERED_STATE = ("DEFAULT_SYMBOLS", "DEFAULT_INTERVAL")


class MarketDataSettingsPresenter(BasePresenter):
    """@brief Presenter for the Market Data settings section."""

    def __init__(self, view: MarketDataSettingsView, container: IContainer) -> None:
        super().__init__(view, container)
        self._settings_view_model = MarketDataSettingsViewModel()
        self._load_from_config()
        self._state_coordinator = find_state_coordinator(container)
        self._settings_view_model.saveRequested.connect(self._on_save)
        view.set_view_model(self._settings_view_model)

    def _load_from_config(self) -> None:
        values = self.config.get_all()
        self._settings_view_model.load_fields(
            default_symbols=f"{_SYMBOL_SEPARATOR} ".join(
                default_symbol_options(values, FALLBACK_SYMBOL_OPTIONS)
            ),
            default_interval=default_interval(values, fallback=FALLBACK_INTERVAL),
            default_sync_days=int(values.get("DEFAULT_SYNC_DAYS") or 1),
            market_data_venue=resolve_market_data_venue(self.config).value,
        )

    @Slot()
    @safe_ui_action
    def _on_save(self) -> None:
        view_model = self._settings_view_model
        symbols = self._parse_symbols(view_model.defaultSymbols)
        if not symbols:
            view_model.set_status(_EMPTY_SYMBOLS_MESSAGE, is_error=True)
            return

        self.config.set(
            ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value, view_model.marketDataVenue
        )
        self.config.set("DEFAULT_SYMBOLS", symbols)
        self.config.set("DEFAULT_INTERVAL", view_model.defaultInterval.strip())
        self.config.set("DEFAULT_SYNC_DAYS", view_model.defaultSyncDays)

        if isinstance(self.config, ConfigManager):
            try:
                self.config.save()
            except (ValueError, OSError) as exc:
                self.logger.error(f"MarketDataSettingsPresenter: save failed: {exc}")
                view_model.set_status(_SAVED_IN_MEMORY_ONLY_MESSAGE, is_error=True)
                return

        self._discard_outranked_state()
        view_model.set_status(_SAVED_MESSAGE, is_error=False)

    def _discard_outranked_state(self) -> None:
        if self._state_coordinator is None:
            return
        for config_key in _CONFIG_KEYS_THAT_OUTRANK_REMEMBERED_STATE:
            self._state_coordinator.discard_for_config_key(config_key)

    @staticmethod
    def _parse_symbols(raw: str) -> list[str]:
        return [part.strip() for part in raw.split(_SYMBOL_SEPARATOR) if part.strip()]
