from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL_OPTIONS,
    default_interval,
    default_symbol_options,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.container_lookup import (
    find_state_coordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .settings_view_model import SettingsViewModel

#: `ActionOwnershipTracker`'s `TKind` — a single action kind exists on this
#: screen today, so a bare string is enough (`async-ui-action-rule.md`
#: doesn't require an enum, only that ownership/fencing exist at all).
_CHECK_CONNECTION_ACTION = "check_connection"

#: `EPIC-010H`'s precedence rule (`ui_state > user_config DEFAULT_*`) means
#: saving one of these two config keys must invalidate whatever remembered
#: field it now outranks. Which screen, and which field — `EPIC-017A`
#: inverted: each screen registers its own binding via
#: `UiStateCoordinator.register_config_binding()` (next to its own
#: `restore_into()` call), instead of Settings holding a hardcoded map of
#: every screen's scope key and field names. This screen only needs to know
#: which of *its own* fields govern others, not who they are.
_CONFIG_KEYS_THAT_OUTRANK_REMEMBERED_STATE = ("DEFAULT_SYMBOLS", "DEFAULT_INTERVAL")

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .settings_view import SettingsView

_SYMBOL_SEPARATOR = ","

_SAVED_MESSAGE = (
    "Đã lưu. Default Symbols/Interval/Sync Days vào user_config.json, "
    "API Key/Secret (nếu có sửa) vào secrets.local.json. Cả hai cần khởi "
    "động lại app để có hiệu lực."
)
_SAVED_IN_MEMORY_ONLY_MESSAGE = (
    "Đã áp dụng cho phiên chạy hiện tại, nhưng KHÔNG ghi được xuống "
    "user_config.json — thay đổi sẽ mất khi khởi động lại app."
)
_EMPTY_SYMBOLS_MESSAGE = "Default Symbols không được để trống."

#: `EPIC-021B` §2.3 — human-readable label per `CredentialsSource`, and
#: whether the field must be locked (an edit that would silently be
#: ignored, because an environment variable always wins, must not be
#: offered as if it would do something).
_CREDENTIALS_SOURCE_LABELS: dict[CredentialsSource, str] = {
    CredentialsSource.ENV: "Đang dùng key từ biến môi trường",
    CredentialsSource.FILE: "Đang dùng key từ secrets.local.json",
    CredentialsSource.NONE: "Chưa cấu hình API key/secret",
}


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

    #: `EPIC-021D` — emitted (from any thread; Qt marshals it to this
    #: QObject's own thread) with `(action_id, ExchangeConnectionStatus |
    #: None, error_message | None)` when a background connection check
    #: finishes.
    connectionCheckCompleted = Signal(tuple)

    def __init__(self, view: SettingsView, container: IContainer) -> None:
        super().__init__(view, container)

        self._credentials_provider: IExchangeCredentialsProvider = container.resolve(
            IExchangeCredentialsProvider
        )
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._connection_check_tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )

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
        self._settings_view_model.checkConnectionRequested.connect(
            self._on_check_connection_requested
        )
        self.connectionCheckCompleted.connect(self._on_connection_check_completed)

    def _connect_engine_events(self) -> None:
        """Nothing to subscribe to — Settings has no background/live data."""

    def _load_from_config(self) -> None:
        # Shows what is actually in effect, not the raw config. Once
        # user_config.json stopped shipping these two keys, reading raw left
        # this screen blank while every other screen ran happily on its floor
        # — and this screen is the user's only view of the value. Resolving is
        # safe precisely because `app_defaults` reads absent and empty the same
        # way, so declared-vs-undeclared has no behaviour to preserve.
        values = self.config.get_all()
        resolution = self._credentials_provider.resolve()
        credentials = resolution.credentials
        self._settings_view_model.load_fields(
            api_key=credentials.api_key if credentials else "",
            api_secret=credentials.api_secret if credentials else "",
            default_symbols=f"{_SYMBOL_SEPARATOR} ".join(
                default_symbol_options(values, FALLBACK_SYMBOL_OPTIONS)
            ),
            default_interval=default_interval(values, fallback=FALLBACK_INTERVAL),
            default_sync_days=int(values.get("DEFAULT_SYNC_DAYS") or 1),
        )
        self._apply_credentials_status(resolution)

    @Slot()
    @safe_ui_action
    def _on_save(self) -> None:
        """
        Validates, then writes every field. Symbols are checked before any
        write so a rejected save never applies partially. Sync days needs no
        check here — the QML SpinBox's `from: 1` already constrains it to a
        positive value.

        API Key/Secret are the one field pair that does NOT go through
        `IConfig.set()` (`EPIC-021B`, closes `BUG-080`'s second, independent
        problem: `user_config.json` is git-tracked, so it must never hold a
        secret). They go to `IExchangeCredentialsProvider.save_to_file()` —
        the gitignored `secrets.local.json` — and only when an environment
        variable is not already winning; a write while `ENV` is in effect
        would be silently ignored by `resolve()`, so it is skipped rather
        than performed and then not shown.
        """
        view_model = self._settings_view_model
        symbols = self._parse_symbols(view_model.defaultSymbols)
        if not symbols:
            view_model.set_status(_EMPTY_SYMBOLS_MESSAGE, is_error=True)
            return

        if not view_model.credentialsLocked:
            try:
                self._credentials_provider.save_to_file(
                    view_model.apiKey, view_model.apiSecret
                )
            except OSError as exc:
                self.logger.error(
                    f"SettingsPresenter: secrets.local.json write failed: {exc}"
                )
                view_model.set_status(_SAVED_IN_MEMORY_ONLY_MESSAGE, is_error=True)
                return
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
        self._refresh_credentials_status()
        view_model.set_status(_SAVED_MESSAGE, is_error=False)

    def _refresh_credentials_status(self) -> None:
        """Re-resolves after a save — a first-time write to
        `secrets.local.json` flips the source from `NONE` to `FILE`, and the
        status label/lock must reflect that immediately, not just after the
        next app restart."""
        self._apply_credentials_status(self._credentials_provider.resolve())

    def _apply_credentials_status(self, resolution: ResolvedCredentials) -> None:
        self._settings_view_model.set_credentials_source(
            _CREDENTIALS_SOURCE_LABELS[resolution.source],
            locked=resolution.source is CredentialsSource.ENV,
        )

    # ------------------------------------------------------------------ #
    # Connection check (`EPIC-021D`) — the screen's one background action.
    # Async ownership per `async-ui-action-rule.md`: an immutable action_id
    # from `ActionOwnershipTracker`, verified still-current before any
    # ViewModel mutation, so a stale callback from a superseded click can
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
        never touch the ViewModel/widgets directly (Qt thread affinity,
        `BUG-031`'s class of defect). Reports back only through
        `connectionCheckCompleted.emit()`, which Qt marshals safely onto
        this Presenter's own thread regardless of which thread emits it.
        """
        try:
            status: ExchangeConnectionStatus = self.dispatcher.dispatch(
                GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQuery()
            )
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
                f"Lỗi kiểm tra kết nối: {error}", is_error=True
            )

    def _discard_outranked_state(self) -> None:
        """Forgets the remembered values this save has just overruled.

        @details `EPIC-010H` settles the three-tier order as

            ui_state  >  user_config DEFAULT_*  >  module constants

        which has one mandatory consequence: a remembered value outranks the
        Settings default, so changing that default must drop the remembered
        one. Without this, the user edits Settings, presses Save, and nothing
        appears to happen — the older, higher-priority value keeps winning.

        `EPIC-017A` — this screen no longer knows which other screens or
        fields that implies; it discards by *config key*, and each screen's
        own `register_config_binding()` call (made once, near its
        `restore_into()`) is what resolves that into scope + field names.
        Dropping whole slices instead would take every unrelated remembered
        value on those screens (leverage, commission, timezone, the script
        checklist) with it, which is why the binding is scoped to fields, not
        screens — unchanged from before the inversion.

        Unconditional rather than compared against the previous value: Save
        is an explicit act, and "make sure this is not remembered" is
        idempotent, so re-saving an unchanged field costs one harmless write
        and needs no before/after bookkeeping to stay correct.
        """
        if self._state_coordinator is None:
            return
        for config_key in _CONFIG_KEYS_THAT_OUTRANK_REMEMBERED_STATE:
            self._state_coordinator.discard_for_config_key(config_key)

    @staticmethod
    def _parse_symbols(raw: str) -> list[str]:
        return [part.strip() for part in raw.split(_SYMBOL_SEPARATOR) if part.strip()]
