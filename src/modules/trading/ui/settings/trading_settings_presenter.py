"""`trading`'s own settings section: credentials, which trading venues are
on, connection check (`EPIC-025E` PR 4.4e; per-venue toggles `EPIC-028C`).

Split off the old monolithic `SettingsPresenter` — this Presenter owns
exactly the fields this module's own ports answer for: the account
connection check (`IAccountSnapshot`), the venue lock (every venue's
`ITradingSession`, `IVenueTradingPorts`),
and this account's credentials (`IExchangeCredentialsProvider`, this
module's own `support/binance_gateway` dependency, unchanged from the
monolith). `market_data`'s venue and sync defaults stay in
`modules/market_data/ui/settings/` instead.

`EPIC-033E`: the section is a page of Tools → Options (`IOptionsSection`).
It saves nothing on its own: the dialog's OK or Apply calls `apply()`, Cancel
calls `revert()`, and the dialog asks `is_dirty()` and
`validation_message()` to enable its buttons.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_trading_venues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels
from Sagittarius_Elite_Warrior.src.support.ui_kit.options_section_presenter import (
    OptionsSectionPresenter,
)
from sagittarius_engine.extensions.pyside_mvc import safe_ui_action
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .trading_settings_view_model import TradingSettingsViewModel

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance
    from sagittarius_engine.interfaces.i_container import IContainer

    from .trading_settings_view import TradingSettingsView

#: `ActionOwnershipTracker`'s `TKind` — a single action kind exists on this
#: section, so a bare string is enough.
_CHECK_CONNECTION_ACTION = "check_connection"

_SAVED_MESSAGE = (
    "Saved. API Key/Secret (if changed) written to secrets.local.json. Both "
    "require restarting the app to take effect."
)
_SECRETS_NOT_SAVED_MESSAGE = (
    "Could not write secrets.local.json, so nothing was changed. Check that "
    "the file is writable, then apply again."
)
_VENUES_NOT_SAVED_MESSAGE = (
    "Could not write user_config.json, so the trading venues were not changed. "
    "Check that the file is writable, then apply again."
)
#: `BOT-125` — a venue change is refused outright rather than partially
#: applied; the dialog keeps OK and Apply disabled and shows this.
_VENUE_LOCKED_MESSAGE = (
    "Trading is active. Disable trading on its desk or the Dev Board "
    "before changing the trading venues."
)
_TITLE = "Trading"

#: `EPIC-021B` §2.3 — human-readable label per `CredentialsSource`, and
#: whether the field must be locked.
_CREDENTIALS_SOURCE_LABELS = EnumLabels(
    CredentialsSource,
    {
        CredentialsSource.ENV: "Using key from environment variable",
        CredentialsSource.FILE: "Using key from secrets.local.json",
        CredentialsSource.NONE: "No API key/secret configured",
    },
)


_Fields = tuple[str, str, tuple[str, ...]]


class TradingSettingsPresenter(OptionsSectionPresenter[_Fields]):
    """@brief Presenter for the Trading settings section."""

    #: `EPIC-021D` — emitted (from any thread; Qt marshals it to this
    #: QObject's own thread) with `(action_id, ExchangeConnectionStatus |
    #: None, error_message | None)` when a background connection check
    #: finishes.
    connectionCheckCompleted = Signal(tuple)

    def __init__(self, view: TradingSettingsView, container: IContainer) -> None:
        super().__init__(view, container, title=_TITLE)
        # `EPIC-028B` — the credentials of the venue this screen configures,
        # the primary one, until each desk has its own settings (`EPIC-028C`).
        self._credentials_provider: IExchangeCredentialsProvider = (
            container.resolve(IVenueContexts).primary().credentials_provider
        )
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        # `BOT-125` — read, never written: the venue toggles are locked while
        # any venue's live session is on (see `_venue_locked()`).
        self._venue_ports: IVenueTradingPorts = container.resolve(IVenueTradingPorts)
        self._account: IAccountSnapshot = container.resolve(IAccountSnapshot)
        self._connection_check_tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )

        self._settings_view_model = TradingSettingsViewModel()
        self._reload()

        self.connectionCheckCompleted.connect(self._on_connection_check_completed)
        self._settings_view_model.checkConnectionRequested.connect(
            self._on_check_connection_requested
        )
        view.set_view_model(self._settings_view_model)

    def _load_from_config(self) -> None:
        resolution = self._credentials_provider.resolve()
        credentials = resolution.credentials
        self._settings_view_model.load_fields(
            api_key=credentials.api_key if credentials else "",
            api_secret=credentials.api_secret if credentials else "",
            enabled_venues=[v.value for v in resolve_trading_venues(self.config)],
        )
        self._settings_view_model.set_venue_locked(self._venue_locked())
        self._apply_credentials_status(resolution)

    def _current_fields(self) -> _Fields:
        view_model = self._settings_view_model
        return (
            view_model.apiKey,
            view_model.apiSecret,
            tuple(sorted(view_model.enabledVenues)),
        )

    def _venues_edited(self) -> bool:
        return self._current_fields()[2] != self._saved_fields[2]

    # -- IOptionsSection (`EPIC-033E`) --------------------------------------

    def validation_message(self) -> str | None:
        if self._venues_edited() and self._venue_locked():
            return _VENUE_LOCKED_MESSAGE
        return None

    def _change_signals(self) -> tuple[SignalInstance, ...]:
        view_model = self._settings_view_model
        return (
            view_model.apiKeyChanged,
            view_model.apiSecretChanged,
            view_model.venueChanged,
        )

    def _venue_locked(self) -> bool:
        """Whether the venue toggles may be edited right now.

        @details Locked while live trading is on for any enabled venue.
        Changing where orders go in the middle of a running session would
        redefine what everything already in flight means (`EPIC-022` §4.1,
        same reasoning as swapping the strategy)."""
        return any(
            self._venue_ports.get(venue).trading_session.snapshot().enabled
            for venue in self._venue_ports.enabled()
        )

    def _save(self) -> bool:
        """Writes the page; `True` when everything reached disk.

        API Key/Secret go to `IExchangeCredentialsProvider.save_to_file()`
        (`EPIC-021B`, `BUG-080`'s second, independent problem:
        `user_config.json` is git-tracked, so a secret must never reach it) —
        only when an environment variable is not already winning; a write
        while `ENV` is in effect would be silently ignored by `resolve()`."""
        view_model = self._settings_view_model

        if not view_model.credentialsLocked:
            try:
                self._credentials_provider.save_to_file(
                    view_model.apiKey, view_model.apiSecret
                )
            except OSError as exc:
                self.logger.error(
                    f"TradingSettingsPresenter: secrets.local.json write failed: {exc}"
                )
                view_model.set_status(_SECRETS_NOT_SAVED_MESSAGE, is_error=True)
                return False
        # `BOT-125` — refuse rather than silently skip. The dialog already
        # keeps OK disabled through `validation_message()`; this guards a
        # session switched on between that check and the write.
        if self._venues_edited():
            if self._venue_locked():
                view_model.set_status(_VENUE_LOCKED_MESSAGE, is_error=True)
                return False
            self._write_trading_venues(view_model.enabledVenues)

        if isinstance(self.config, ConfigManager):
            try:
                self.config.save()
            except (ValueError, OSError) as exc:
                self.logger.error(
                    f"TradingSettingsPresenter: config save failed: {exc}"
                )
                view_model.set_status(_VENUES_NOT_SAVED_MESSAGE, is_error=True)
                return False

        self._refresh_credentials_status()
        view_model.set_status(_SAVED_MESSAGE, is_error=False)
        return True

    def _undo_unsaved_writes(self) -> None:
        """The venues go back to the saved list. The credentials are what
        `secrets.local.json` now holds: a failed config write can follow a
        secrets write that succeeded, and that one is saved."""
        saved_venues = self._saved_fields[2]
        if self._venues_edited():
            self._write_trading_venues(list(saved_venues))
        credentials = self._credentials_provider.resolve().credentials
        self._saved_fields = (
            credentials.api_key if credentials else "",
            credentials.api_secret if credentials else "",
            saved_venues,
        )

    def _write_trading_venues(self, enabled: list[str]) -> None:
        """`EPIC-028C` — the list is what boot reads (`resolve_trading_venues`),
        in `TradingVenue` order so the primary venue does not depend on the
        order the boxes were ticked. `IConfig` cannot delete a key and the
        defaults file always carries the legacy scalar, so it is kept in
        step with the list's primary venue rather than left contradicting it."""
        venues = [venue.value for venue in TradingVenue if venue.value in enabled]
        self.config.set(ConfigKeys.EXCHANGE_TRADING_VENUES.value, venues)
        self.config.set(
            ConfigKeys.EXCHANGE_TRADING_VENUE.value,
            venues[0] if venues else TradingVenue.DISABLED.value,
        )

    def _refresh_credentials_status(self) -> None:
        """Re-resolves after a save — a first-time write to
        `secrets.local.json` flips the source from `NONE` to `FILE`, and the
        status label/lock must reflect that immediately."""
        self._apply_credentials_status(self._credentials_provider.resolve())

    def _apply_credentials_status(self, resolution: ResolvedCredentials) -> None:
        self._settings_view_model.set_credentials_source(
            _CREDENTIALS_SOURCE_LABELS[resolution.source],
            locked=resolution.source is CredentialsSource.ENV,
        )

    # ------------------------------------------------------------------ #
    # Connection check (`EPIC-021D`) — this section's one background
    # action. Async ownership per `async-ui-action-rule.md`: an immutable
    # action_id from `ActionOwnershipTracker`, verified still-current before
    # any ViewModel mutation, so a stale callback from a superseded click can
    # never overwrite a newer one.
    # ------------------------------------------------------------------ #

    @Slot()
    @safe_ui_action
    def _on_check_connection_requested(self) -> None:
        action = self._connection_check_tracker.begin_action(
            _CHECK_CONNECTION_ACTION, None, None
        )
        self._settings_view_model.set_connection_checking(True)
        self._thread_manager.submit(self._run_check_connection, action.action_id)

    def _run_check_connection(self, action_id: int) -> None:
        """Runs on a background thread (`IThreadManager`'s pool) — must
        never touch the ViewModel/widgets directly (`BUG-031`'s class of
        defect). Reports back only through `connectionCheckCompleted.emit()`,
        which Qt marshals safely onto this Presenter's own thread."""
        try:
            status: ExchangeConnectionStatus = self._account.check_connection()
            self.connectionCheckCompleted.emit((action_id, status, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self.connectionCheckCompleted.emit((action_id, None, str(exc)))

    def _on_connection_check_completed(self, payload: tuple) -> None:
        action_id, status, error = payload
        if not self._connection_check_tracker.is_current_pending(
            action_id, _CHECK_CONNECTION_ACTION
        ):
            self._connection_check_tracker.log_stale_callback(
                "check_connection", action_id, _CHECK_CONNECTION_ACTION
            )
            return

        if status is not None:
            self._connection_check_tracker.finish_action(
                action_id, ActionOutcome.SUCCEEDED
            )
            self._settings_view_model.set_connection_result(
                format_exchange_connection_status(status),
                is_error=status.failure is not None,
            )
        else:
            self._connection_check_tracker.finish_action(
                action_id, ActionOutcome.FAILED
            )
            self._settings_view_model.set_connection_result(
                f"Connection check error: {error}", is_error=True
            )
