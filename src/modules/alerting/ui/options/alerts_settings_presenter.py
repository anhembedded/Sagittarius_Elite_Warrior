"""`alerting`'s page of Tools → Options: the Discord webhook (`EPIC-036D1`) and the Telegram
bot (`EPIC-036D4`).

The owner saves, removes, replaces or tests a channel. Every decision lives in the
application layer (`DiscordWebhookSetup`, `TelegramCredentialsSetup` validate and store,
`SendTestToConfiguredChannels` asks the channels), so this presenter stores and probes
nothing, and holds a typed secret only between the click and the worker that hands it on.

**A webhook URL and a bot token are secrets (N3), so no exception text from these actions
reaches a screen or a log.** An unexpected failure is told by its type name alone, because an
exception raised under a webhook can quote it and `failure_detail(exc)` would pass that text to
Details… and a log's traceback would print it. `test_alerts_page_never_shows_the_url.py` and
`test_alerts_page_telegram.py` lock it.

The page has nothing pending: each channel is saved by its own button, so it is never dirty
and OK and Apply have nothing to do. Each action runs off the UI thread under
`async-ui-action-rule.md` (an `ActionOwnershipTracker` id checked before the view model
changes, a `UiThreadRelay` hand-off, buttons disabled while one runs; `shutdown()` fences
any answer still in flight).

**Restart or hot rebuild: restart** (`Docs/MODULES/alerting/06-runtime.md`). A saved secret is
read at each send, so a replaced one applies at once; the catalog and the lanes are fixed at
boot, so a first save or a removal changes what the run has only after a restart, and the page
says so (`alerts_words.channel_line`, `alerts_words.telegram_channel_line`).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import time
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Slot
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channels_setup import (
    ChannelsSetup,
    ChannelSwitch,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordWebhookSetup,
    WebhookRemoval,
    WebhookSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.quiet_hours_setup import (
    QuietHoursSave,
    QuietHoursSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.routing_setup import (
    RouteSave,
    RoutingSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
    ChannelTestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_to_configured_channels import (
    SendTestToConfiguredChannels,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_credentials_setup import (
    TelegramCredentialsSetup,
    TelegramRemoval,
    TelegramSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_routing import (
    IAlertRouting,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_channel_enabling import (
    IChannelEnabling,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    IQuietHoursSetting,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.action_results import (
    ActionResults,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_action_kind import (
    AlertsActionKind,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_action_relay import (
    AlertsActionRelay,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
    BotModeRow,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.bot_mode_list import (
    BotModeList,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.channel_states import (
    ChannelStates,
    read_channel_states,
    show_channel_states,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.display_zone_key import (
    display_zone_key_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.options_section_presenter import (
    OptionsSectionPresenter,
)
from sagittarius_engine.extensions.pyside_mvc import safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance
    from sagittarius_engine.interfaces.i_container import IContainer

    from .alerts_settings_view import AlertsSettingsView

_TITLE = "Alerts"


class AlertsSettingsPresenter(OptionsSectionPresenter[tuple[()]]):
    """@brief Presenter for the Alerts settings section."""

    def __init__(self, view: AlertsSettingsView, container: IContainer) -> None:
        super().__init__(view, container, title=_TITLE)
        self._setup: DiscordWebhookSetup = container.resolve(DiscordWebhookSetup)
        self._telegram_setup: TelegramCredentialsSetup = container.resolve(
            TelegramCredentialsSetup
        )
        self._sender: SendTestToConfiguredChannels = container.resolve(
            SendTestToConfiguredChannels
        )
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._tracker: ActionOwnershipTracker[AlertsActionKind, None, None] = (
            ActionOwnershipTracker()
        )
        self._relay = AlertsActionRelay(self._on_action_done)

        self._settings_view_model = AlertsSettingsViewModel()
        self._routing = RoutingSetup(
            container.resolve(IAlertRouting), container.resolve(IAlertChannelCatalog)
        )
        self._channels = ChannelsSetup(
            container.resolve(IChannelEnabling), container.resolve(IAlertChannelCatalog)
        )
        self._quiet = QuietHoursSetup(
            container.resolve(IQuietHoursSetting), display_zone_key_of(container)
        )
        self._results = ActionResults(
            self._settings_view_model, container.resolve(INotifier), self.logger
        )
        self._bots = BotModeList(
            container.resolve(IBotAlertModes),
            container.resolve(ICommandDispatcher),
            self._settings_view_model,
        )
        self._tell = self._tellers()
        self._reload()
        self._begin(AlertsActionKind.BOTS, self._bots.bots_with_modes)

        view_model = self._settings_view_model
        view_model.save_requested.connect(self._on_save_requested)
        view_model.remove_requested.connect(self._on_remove_requested)
        view_model.telegram.save_requested.connect(self._on_telegram_save_requested)
        view_model.telegram.remove_requested.connect(self._on_telegram_remove_requested)
        view_model.send_test_requested.connect(self._on_send_test_requested)
        view_model.routing.cell_requested.connect(self._on_route_requested)
        view_model.channels.switch_requested.connect(self._on_channel_requested)
        view_model.quiet.period_requested.connect(self._on_quiet_period_requested)
        view_model.quiet.turn_off_requested.connect(self._on_quiet_turn_off_requested)
        view_model.bot_mode_requested.connect(self._on_bot_mode_requested)
        view.set_view_model(view_model)

    def shutdown(self) -> None:
        """Answers still in flight are dropped, and none is delivered after this."""
        self._tracker.invalidate_active()
        self._relay.stop_delivering()
        super().shutdown()

    # -- IOptionsSection ----------------------------------------------------

    def _load_from_config(self) -> None:
        self._publish_state()
        self._settings_view_model.routing.take_state(self._routing.state())
        self._settings_view_model.channels.take_state(self._channels.state())
        self._settings_view_model.quiet.take_state(self._quiet.state())

    def _current_fields(self) -> tuple[()]:
        return ()

    def _change_signals(self) -> tuple[SignalInstance, ...]:
        return ()

    def _save(self) -> bool:
        """Nothing is pending: every change was saved by the button that made it."""
        return True

    def _undo_unsaved_writes(self) -> None:
        """`_save` writes nothing, so there is nothing to take back."""

    # -- the state on the page ----------------------------------------------

    def _read_states(self) -> ChannelStates:
        return read_channel_states(self._setup, self._telegram_setup, self._channels)

    def _publish_state(self, states: ChannelStates | None = None) -> None:
        """Shows `states`; the page's first state is read here, on the UI thread, once.
        Every later one is read by the worker beside its action, because reading
        the stores can block on a locked keyring."""
        show_channel_states(
            self._settings_view_model,
            states if states is not None else self._read_states(),
        )

    # -- user requests ------------------------------------------------------

    @Slot(str, str)
    @safe_ui_action
    def _on_bot_mode_requested(self, bot_id: str, value: str) -> None:
        if self._settings_view_model.is_working or self._bots.read_only:
            return
        try:
            mode = BotAlertMode(value)
        except ValueError:
            return
        self._begin(AlertsActionKind.MODE, lambda: self._bots.keep(bot_id, mode))

    @Slot(object, str, object)
    @safe_ui_action
    def _on_route_requested(
        self, group: AlertGroup, channel_id: str, loudness: Loudness | None
    ) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(
            AlertsActionKind.ROUTE,
            lambda: self._routing.set_cell(group, channel_id, loudness),
        )

    @Slot(str, bool)
    @safe_ui_action
    def _on_channel_requested(self, channel_id: str, on: bool) -> None:
        if self._settings_view_model.is_working:
            return
        switch = self._channels.turn_on if on else self._channels.turn_off
        self._begin(AlertsActionKind.CHANNEL, lambda: switch(channel_id))

    @Slot(object, object)
    @safe_ui_action
    def _on_quiet_period_requested(self, start: time, end: time) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(AlertsActionKind.QUIET, lambda: self._quiet.set_period(start, end))

    @Slot()
    @safe_ui_action
    def _on_quiet_turn_off_requested(self) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(AlertsActionKind.QUIET, self._quiet.turn_off)

    @Slot(str)
    @safe_ui_action
    def _on_save_requested(self, value: str) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(AlertsActionKind.SAVE, lambda: self._setup.save(value))

    @Slot(str, str)
    @safe_ui_action
    def _on_telegram_save_requested(self, token: str, chat: str) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(
            AlertsActionKind.TELEGRAM_SAVE,
            lambda: self._telegram_setup.save(token, chat),
        )

    @Slot()
    @safe_ui_action
    def _on_telegram_remove_requested(self) -> None:
        if (
            self._settings_view_model.is_working
            or not self.view.confirm_telegram_removal()
        ):
            return
        self._begin(AlertsActionKind.TELEGRAM_REMOVE, self._telegram_setup.remove)

    @Slot()
    @safe_ui_action
    def _on_remove_requested(self) -> None:
        if self._settings_view_model.is_working or not self.view.confirm_removal():
            return
        self._begin(AlertsActionKind.REMOVE, self._setup.remove)

    @Slot()
    @safe_ui_action
    def _on_send_test_requested(self) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(AlertsActionKind.TEST, self._sender.run)

    # -- background actions -------------------------------------------------

    def _begin(self, kind: AlertsActionKind, work: Callable[[], object]) -> None:
        action = self._tracker.begin_action(kind, None, None)
        self._settings_view_model.set_status("", False)
        self._settings_view_model.set_working(alerts_words.WORKING_WORDS[kind.value])
        self._thread_manager.submit(self._work_on_pool, action.action_id, kind, work)

    def _work_on_pool(
        self, action_id: int, kind: AlertsActionKind, work: Callable[[], object]
    ) -> None:
        """Runs on the thread pool: never touches the view model or a widget
        (`BUG-031`'s class of defect); reports back through the relay. A failure is
        reported by its type name only (see the module docstring)."""
        try:
            result = work()
            self._relay.hand_over((action_id, kind, result, self._read_states(), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: the failure is told in words, not lost to a pool thread
            self._relay.hand_over((action_id, kind, None, None, type(exc).__name__))

    def _on_action_done(self, payload: tuple) -> None:
        """Runs on the UI thread with what the worker reported. The fence
        (`is_current_pending`) is defence in depth: the buttons are off while an
        action runs, so only `shutdown()` and a test can make an answer stale."""
        action_id, kind, result, state, error_type = payload
        if not self._tracker.is_current_pending(action_id, kind):
            self._tracker.log_stale_callback(kind.value, action_id, kind)
            return
        failed = error_type is not None
        self._tracker.finish_action(
            action_id, ActionOutcome.FAILED if failed else ActionOutcome.SUCCEEDED
        )
        self._settings_view_model.set_working("")
        if state is not None:
            self._publish_state(state)
        if kind is AlertsActionKind.MODE:
            self._bots.show_again()
        self._reshow_kept(kind)
        if failed:
            self._on_action_failed(kind, error_type)
        else:
            self._tell[kind](result)

    def _on_action_failed(self, kind: AlertsActionKind, error_type: str) -> None:
        if kind is AlertsActionKind.BOTS:
            self._settings_view_model.set_bot_rows((), alerts_words.BOTS_UNREADABLE)
        else:
            self._results.failed(kind.value, error_type)

    def _reshow_kept(self, kind: AlertsActionKind) -> None:
        """A combo or a box shows what was kept, not what was picked: after a success and after
        a failure alike."""
        view_model = self._settings_view_model
        if kind is AlertsActionKind.ROUTE:
            view_model.routing.take_state(self._routing.state())
        elif kind is AlertsActionKind.CHANNEL:
            view_model.channels.take_state(self._channels.state())

    def _quiet_kept(self, outcome: QuietHoursSave) -> None:
        self._results.quiet_kept(outcome)
        if outcome is not QuietHoursSave.NO_PERIOD:  # a refused period stays typed
            self._settings_view_model.quiet.take_state(self._quiet.state())

    def _tellers(self) -> dict[AlertsActionKind, Callable[[object], None]]:
        """What each action's answer is told as; the argument is what that kind's work returned."""
        kind, results = AlertsActionKind, self._results
        return {
            kind.BOTS: lambda r: self._bots.publish_rows(
                cast(tuple[BotModeRow, ...], r)
            ),
            kind.SAVE: lambda r: results.webhook_kept(cast(WebhookSave, r)),
            kind.REMOVE: lambda r: results.webhook_forgotten(cast(WebhookRemoval, r)),
            kind.TELEGRAM_SAVE: lambda r: results.telegram_kept(cast(TelegramSave, r)),
            kind.TELEGRAM_REMOVE: lambda r: results.telegram_forgotten(
                cast(TelegramRemoval, r)
            ),
            kind.ROUTE: lambda r: results.route_kept(cast(RouteSave, r)),
            kind.CHANNEL: lambda r: results.channel_switched(cast(ChannelSwitch, r)),
            kind.QUIET: lambda r: self._quiet_kept(cast(QuietHoursSave, r)),
            kind.MODE: lambda r: results.mode_kept(cast(BotAlertMode, r)),
            kind.TEST: lambda r: results.test_sent(
                cast(tuple[ChannelTestOutcome, ...], r)
            ),
        }
