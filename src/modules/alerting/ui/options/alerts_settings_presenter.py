"""`alerting`'s page of Tools → Options: the Discord webhook (`EPIC-036D1`).

The owner pastes a webhook URL, saves it, removes it, or sends a test message. Every
decision lives in the application layer — `DiscordWebhookSetup` validates and stores,
`SendTestToConfiguredChannels` asks Discord — so this presenter stores and probes
nothing, and holds the typed URL only between the click and the worker that hands it
to the use case.

**The URL is a secret (N3), so no exception text from these actions reaches a
screen or a log.** An unexpected failure is told by its type name alone
(`type(exc).__name__`), because an exception raised under a webhook can quote the
webhook (`ValueError("... https://discord.com/api/webhooks/…")`), and
`failure_detail(exc)` would pass that text to Details… and a log's traceback would
print it. `test_alerts_page_never_shows_the_url.py` locks it on every path.

The page has nothing pending (like Trading's): a webhook is saved by its button, so
the page is never dirty and OK and Apply have nothing to do. Each action runs off the
UI thread under `async-ui-action-rule.md`: an `ActionOwnershipTracker` id checked
still-current before the view model changes, a `UiThreadRelay` hand-off, and the
buttons disabled while one runs. `shutdown()` fences any answer still in flight.

**Restart or hot rebuild: restart** (`Docs/MODULES/alerting/06-runtime.md`). A saved
webhook is read at each send, so a replaced one applies at once; but the channel
catalog and the lanes are fixed at boot, so a first save or a removal changes what the
run has only after a restart, and the page says so
(`alerts_words.channel_line`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from enum import Enum
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Slot
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordChannelState,
    DiscordWebhookSetup,
    WebhookRemoval,
    WebhookSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_to_configured_channels import (
    SendTestToConfiguredChannels,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_action_relay import (
    AlertsActionRelay,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
    BotModeRow,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
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

#: `BOT-169` — the causes of the page's commands, one message each.
_CAUSE = "alerting.settings.{kind}"


class _Kind(str, Enum):
    """`ActionOwnershipTracker`'s `TKind`: the three things the page runs off the UI thread."""

    SAVE = "save"
    REMOVE = "remove"
    TEST = "test"
    MODE = "mode"
    BOTS = "bots"


_DOING = {
    _Kind.SAVE: "Saving the webhook",
    _Kind.REMOVE: "Removing the webhook",
    _Kind.TEST: "Sending the test message",
    _Kind.MODE: "Saving the bot's alert setting",
    _Kind.BOTS: "Reading the bots",
}


class AlertsSettingsPresenter(OptionsSectionPresenter[tuple[()]]):
    """@brief Presenter for the Alerts settings section."""

    def __init__(self, view: AlertsSettingsView, container: IContainer) -> None:
        super().__init__(view, container, title=_TITLE)
        self._notifier: INotifier = container.resolve(INotifier)
        self._setup: DiscordWebhookSetup = container.resolve(DiscordWebhookSetup)
        self._sender: SendTestToConfiguredChannels = container.resolve(
            SendTestToConfiguredChannels
        )
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._modes: IBotAlertModes = container.resolve(IBotAlertModes)
        self._dispatcher: ICommandDispatcher = container.resolve(ICommandDispatcher)
        self._tracker: ActionOwnershipTracker[_Kind, None, None] = (
            ActionOwnershipTracker()
        )
        self._relay = AlertsActionRelay(self._on_action_done)

        self._settings_view_model = AlertsSettingsViewModel()
        self._reload()
        self._begin(_Kind.BOTS, self._list_bots)

        view_model = self._settings_view_model
        view_model.save_requested.connect(self._on_save_requested)
        view_model.remove_requested.connect(self._on_remove_requested)
        view_model.send_test_requested.connect(self._on_send_test_requested)
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

    def _publish_state(self, state: DiscordChannelState | None = None) -> None:
        """Shows `state`; the page's first state is read here, on the UI thread, once.
        Every later one is read by the worker beside its action, because reading
        the stores can block on a locked keyring."""
        state = state if state is not None else self._setup.state()
        self._settings_view_model.set_channel(
            alerts_words.channel_line(state),
            alerts_words.saved_line(state),
            can_remove=state.stored,
            can_test=state.usable,
        )

    def _list_bots(self) -> tuple[BotModeRow, ...]:
        """`BOT-191`: the bots the page can set, each with what it may tell now. Runs on the
        pool: the report reads every bot's file."""
        report = cast(
            BotStatusReport,
            self._dispatcher.dispatch(
                GetBotStatusReportQuery, GetBotStatusReportQuery()
            ),
        )
        modes = self._modes.modes()
        return tuple(
            BotModeRow(
                entry.bot_id,
                entry.name,
                modes.get(entry.bot_id, BotAlertMode.ON).value,
            )
            for entry in report.bots
        )

    def _publish_bot_rows(self, rows: tuple[BotModeRow, ...]) -> None:
        read_only = self._modes.read_only
        note = (
            alerts_words.READ_ONLY_NOTE
            if read_only
            else ("" if rows else alerts_words.NO_BOTS)
        )
        self._settings_view_model.set_bot_rows(rows, note, editable=not read_only)

    def _show_modes_again(self) -> None:
        """Memory only: the same bots, each with the mode really kept now."""
        modes = self._modes.modes()
        self._publish_bot_rows(
            tuple(
                replace(row, mode=modes.get(row.bot_id, BotAlertMode.ON).value)
                for row in self._settings_view_model.bot_rows
            )
        )

    # -- user requests ------------------------------------------------------

    @Slot(str, str)
    @safe_ui_action
    def _on_bot_mode_requested(self, bot_id: str, value: str) -> None:
        if self._settings_view_model.is_working or self._modes.read_only:
            return
        try:
            mode = BotAlertMode(value)
        except ValueError:
            return
        self._begin(_Kind.MODE, lambda: self._after_mode(bot_id, mode))

    @Slot(str)
    @safe_ui_action
    def _on_save_requested(self, value: str) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(_Kind.SAVE, lambda: self._setup.save(value))

    @Slot()
    @safe_ui_action
    def _on_remove_requested(self) -> None:
        if self._settings_view_model.is_working or not self.view.confirm_removal():
            return
        self._begin(_Kind.REMOVE, self._setup.remove)

    @Slot()
    @safe_ui_action
    def _on_send_test_requested(self) -> None:
        if self._settings_view_model.is_working:
            return
        self._begin(_Kind.TEST, self._sender.run)

    # -- background actions -------------------------------------------------

    def _begin(self, kind: _Kind, work: Callable[[], object]) -> None:
        action = self._tracker.begin_action(kind, None, None)
        self._settings_view_model.set_status("", False)
        self._settings_view_model.set_working(alerts_words.WORKING_WORDS[kind.value])
        self._thread_manager.submit(self._work_on_pool, action.action_id, kind, work)

    def _work_on_pool(
        self, action_id: int, kind: _Kind, work: Callable[[], object]
    ) -> None:
        """Runs on the thread pool: never touches the view model or a widget
        (`BUG-031`'s class of defect); reports back through the relay. A failure is
        reported by its type name only (see the module docstring)."""
        try:
            result = work()
            self._relay.hand_over((action_id, kind, result, self._setup.state(), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: the failure is told in words, not lost to a pool thread
            self._relay.hand_over((action_id, kind, None, None, type(exc).__name__))

    def _after_mode(self, bot_id: str, mode: BotAlertMode) -> BotAlertMode:
        self._modes.set_mode(bot_id, mode)
        return mode

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
        if kind is _Kind.MODE:
            self._show_modes_again()
        if failed and kind is _Kind.BOTS:
            self._settings_view_model.set_bot_rows((), alerts_words.BOTS_UNREADABLE)
        elif failed:
            self._tell_failed(kind, error_type)
        elif kind is _Kind.BOTS:
            self._publish_bot_rows(result)
        elif kind is _Kind.SAVE:
            self._on_webhook_saved(result)
        elif kind is _Kind.REMOVE:
            self._on_webhook_removed(result)
        elif kind is _Kind.MODE:
            self._settings_view_model.set_status(alerts_words.MODE_SAVED[result], False)
        else:
            sentence, is_error = alerts_words.send_test_words(result)
            self._settings_view_model.set_status(sentence, is_error)

    def _on_webhook_saved(self, outcome: WebhookSave) -> None:
        sentence, is_error = alerts_words.SAVE_WORDS[outcome]
        if outcome in (WebhookSave.SAVED, WebhookSave.OVERRIDDEN):
            self._settings_view_model.keep_webhook()
        self._settings_view_model.set_status(sentence, is_error)

    def _on_webhook_removed(self, outcome: WebhookRemoval) -> None:
        sentence, is_error = alerts_words.REMOVAL_WORDS[outcome]
        self._settings_view_model.set_status(sentence, is_error)

    # -- failures -----------------------------------------------------------

    def _tell_failed(self, kind: _Kind, error_type: str) -> None:
        """A command the user just ran did not do what they asked (`BOT-169`): a
        message box, with only the exception's type behind Details…."""
        self.logger.warning(
            f"AlertsSettingsPresenter: {kind.value} raised {error_type} [alert-setup]"
        )
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.COMMAND,
                cause=_CAUSE.format(kind=kind.value),
                headline=alerts_words.UNEXPECTED_HEADLINE.format(doing=_DOING[kind]),
                detail=error_type,
            )
        )
