"""`trading`'s own settings section: the keys of the four venues (`EPIC-025E` PR 4.4e,
`EPIC-034B`, `BUG-176`).

The page lists one row per venue (key fingerprint, connection state, Replace and
Remove) and has one way in, Add key…: the user gives a key and a secret and never
says which environment it is from. Everything that is a decision lives in the
application layer — `EnrolKeyCommand` asks Binance, applies the withdrawal gate and
stores per venue; `RemoveKeyCommand`, `ListVenueKeysQuery` and
`GetExchangeConnectionStatusQuery` serve the rest — so this presenter probes and
stores nothing, and holds no key or secret beyond the instant between the dialog
and the command.

`EPIC-033E`: the section is a page of Tools → Options (`IOptionsSection`). It has
nothing pending: a key is saved when it is added, replaced or removed, so the page
is never dirty and OK and Apply have nothing to do here.

Each action runs off the UI thread under `async-ui-action-rule.md`: an action id from
`ActionOwnershipTracker`, checked still-current before the view model changes, and
the buttons disabled while one runs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.enrol_key import (
    EnrolKeyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.remove_key import (
    RemoveKeyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.list_venue_keys import (
    ListVenueKeysQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    KeyEnrolment,
    KeyRemoval,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_key import VenueKey
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.connection_state_words import (
    NO_KEY,
    NOT_CHECKED,
    state_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.key_enrolment_words import (
    kept_message,
    refusal_detail,
    refusal_headline,
    removal_failure_headline,
    venues_in_words,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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

from .trading_settings_view_model import KeyRow, TradingSettingsViewModel

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance
    from sagittarius_engine.interfaces.i_container import IContainer

    from .trading_settings_view import TradingSettingsView

_TITLE = "Trading"

#: `ActionOwnershipTracker`'s `TKind`: the three things this page runs off the UI thread.
_ENROL = "enrol_key"
_REMOVE = "remove_key"
_CHECK = "check_connections"

#: `BOT-169` — the causes of the page's commands, one message each.
_ENROL_CAUSE = "trading.settings.add_key"
_REMOVE_CAUSE = "trading.settings.remove_key"
_CHECK_CAUSE = "trading.settings.check_connections"

_SOURCE_WORDS = {
    CredentialsSource.ENV: "environment variable",
    CredentialsSource.FILE: "secrets.local.json",
    CredentialsSource.KEYRING: "OS keyring",
    CredentialsSource.NONE: "",
}
_ADD_HINT = (
    "Enter the key and its secret. The app asks Binance which environment the "
    "key belongs to and keeps it for the venues it can trade."
)
_REPLACE_HINT = "Enter the new key and secret for {venue}. It must be a key of {venue}."
_UNEXPECTED_HEADLINE = (
    "{doing} failed unexpectedly. Nothing was changed that this page can tell; "
    "check the log, then try again."
)


class TradingSettingsPresenter(OptionsSectionPresenter[tuple[()]]):
    """@brief Presenter for the Trading settings section."""

    #: Emitted from the worker thread (Qt marshals it to this QObject's thread) with
    #: `(action_id, kind, result | None, detail | None)` when an action finishes.
    actionCompleted = Signal(tuple)

    def __init__(self, view: TradingSettingsView, container: IContainer) -> None:
        super().__init__(view, container, title=_TITLE)
        self._notifier: INotifier = container.resolve(INotifier)
        self._dispatcher: ICommandDispatcher = container.resolve(ICommandDispatcher)
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )
        #: What the last check said of each venue; a venue is "not checked" until then.
        self._states: dict[TradingVenue, tuple[str, bool]] = {}
        self._keys: tuple[VenueKey, ...] = ()
        #: The venue Replace / Add… was pressed on, while its dialog's key is being checked.
        self._target: TradingVenue | None = None
        #: What adding a key said, told again with the connection check that follows it.
        self._kept = ""

        self._settings_view_model = TradingSettingsViewModel()
        self._reload()

        self.actionCompleted.connect(self._on_action_completed)
        view_model = self._settings_view_model
        view_model.addKeyRequested.connect(self._on_add_key_requested)
        view_model.replaceKeyRequested.connect(self._on_replace_key_requested)
        view_model.removeKeyRequested.connect(self._on_remove_key_requested)
        view_model.checkConnectionsRequested.connect(self._on_check_requested)
        view.set_view_model(view_model)

    # -- IOptionsSection ----------------------------------------------------

    def _load_from_config(self) -> None:
        self._keys = self._read_keys()
        self._publish_rows()

    def _current_fields(self) -> tuple[()]:
        return ()

    def _change_signals(self) -> tuple[SignalInstance, ...]:
        return ()

    def _save(self) -> bool:
        """Nothing is pending: every change was saved by the action that made it."""
        return True

    def _undo_unsaved_writes(self) -> None:
        """Nothing is written by `_save`, so nothing to take back."""

    # -- rows ---------------------------------------------------------------

    def _read_keys(self) -> tuple[VenueKey, ...]:
        return cast(
            "tuple[VenueKey, ...]",
            self._dispatcher.dispatch(ListVenueKeysQuery, ListVenueKeysQuery()),
        )

    def _publish_rows(self) -> None:
        self._settings_view_model.set_rows(tuple(self._row_of(k) for k in self._keys))

    def _row_of(self, key: VenueKey) -> KeyRow:
        has_key = key.fingerprint is not None
        if has_key:
            where = _SOURCE_WORDS[key.source]
            shown = f"{key.fingerprint} ({where})"
            state, is_error = self._states.get(key.venue, (NOT_CHECKED, False))
        else:
            shown = "—"
            state, is_error = NO_KEY, False
        return KeyRow(
            venue=key.venue,
            title=key.venue.display_name,
            key=shown,
            state=state,
            state_is_error=is_error,
            has_key=has_key,
            editable=key.source is not CredentialsSource.ENV,
        )

    # -- user requests ------------------------------------------------------

    @Slot()
    @safe_ui_action
    def _on_add_key_requested(self) -> None:
        self._ask_then_enrol(None, _ADD_HINT)

    @Slot(object)
    @safe_ui_action
    def _on_replace_key_requested(self, venue: TradingVenue) -> None:
        self._ask_then_enrol(venue, _REPLACE_HINT.format(venue=venue.display_name))

    def _ask_then_enrol(self, target: TradingVenue | None, hint: str) -> None:
        if self._settings_view_model.busy:
            return
        entered = self.view.ask_for_key(hint)
        if entered is None:
            return
        command = EnrolKeyCommand(ExchangeCredentials(*entered), only_for=target)
        self._target = target
        self._begin(
            _ENROL,
            "Asking Binance which environment the key belongs to…",
            lambda: self._dispatcher.dispatch(EnrolKeyCommand, command),
        )

    @Slot(object)
    @safe_ui_action
    def _on_remove_key_requested(self, venue: TradingVenue) -> None:
        if self._settings_view_model.busy:
            return
        command = RemoveKeyCommand(venue=venue)
        self._begin(
            _REMOVE,
            f"Removing the {command.venue.display_name} key…",
            lambda: self._dispatcher.dispatch(RemoveKeyCommand, command),
        )

    @Slot()
    @safe_ui_action
    def _on_check_requested(self) -> None:
        if self._settings_view_model.busy:
            return
        self._begin_check(
            tuple(k.venue for k in self._keys if k.fingerprint is not None)
        )

    def _begin_check(self, venues: tuple[TradingVenue, ...]) -> None:
        self._begin(
            _CHECK,
            "Checking the connection to Binance…",
            lambda: {
                venue: self._dispatcher.dispatch(
                    GetExchangeConnectionStatusQuery,
                    GetExchangeConnectionStatusQuery(venue=venue),
                )
                for venue in venues
            },
        )

    # -- background actions -------------------------------------------------

    def _begin(self, kind: str, busy_text: str, work: Callable[[], object]) -> None:
        action = self._tracker.begin_action(kind, None, None)
        self._settings_view_model.set_status("", False)
        self._settings_view_model.set_busy(busy_text)
        self._thread_manager.submit(self._run, action.action_id, kind, work)

    def _run(self, action_id: int, kind: str, work: Callable[[], object]) -> None:
        """Runs on the thread pool: never touches the view model or a widget
        (`BUG-031`'s class of defect); reports back through `actionCompleted`."""
        try:
            self.actionCompleted.emit((action_id, kind, work(), None))
        except Exception as exc:
            self.logger.warning(
                f"TradingSettingsPresenter: {kind} {action_id} raised", exc_info=True
            )
            self.actionCompleted.emit((action_id, kind, None, failure_detail(exc)))

    def _on_action_completed(self, payload: tuple) -> None:
        action_id, kind, result, detail = payload
        if not self._tracker.is_current_pending(action_id, kind):
            self._tracker.log_stale_callback(kind, action_id, kind)
            return
        failed = detail is not None
        self._tracker.finish_action(
            action_id, ActionOutcome.FAILED if failed else ActionOutcome.SUCCEEDED
        )
        self._settings_view_model.set_busy("")
        if failed:
            self._tell_unexpected(kind, detail)
        elif kind == _ENROL:
            self._on_enrolled(result)
        elif kind == _REMOVE:
            self._on_removed(result)
        else:
            self._on_checked(result)

    def _on_enrolled(self, enrolment: KeyEnrolment) -> None:
        target, self._target = self._target, None
        self._load_from_config()
        if enrolment.refusal is not None:
            self.logger.info(
                "TradingSettingsPresenter: key not kept: "
                f"{enrolment.refusal.value} [key-enrolment]"
            )
            self._tell_command_failed(
                _ENROL_CAUSE,
                refusal_headline(enrolment, target),
                refusal_detail(enrolment),
            )
            return
        for venue in enrolment.stored:
            self._states.pop(venue, None)
        self.logger.info(
            "TradingSettingsPresenter: key kept for "
            f"{[v.name for v in enrolment.stored]} [key-enrolment]"
        )
        self._kept = kept_message(enrolment)
        self._publish_rows()
        self._begin_check(enrolment.stored)

    def _on_removed(self, removal: KeyRemoval) -> None:
        self._load_from_config()
        self.logger.info(
            f"TradingSettingsPresenter: key removal {removal.value} [key-enrolment]"
        )
        if removal in (KeyRemoval.REMOVED, KeyRemoval.NOTHING_STORED):
            self._settings_view_model.set_status("Key removed.", False)
            return
        self._tell_command_failed(
            _REMOVE_CAUSE, removal_failure_headline(removal), removal.value
        )

    def _on_checked(
        self, statuses: dict[TradingVenue, ExchangeConnectionStatus]
    ) -> None:
        for venue, status in statuses.items():
            self._states[venue] = state_of(status)
        self._publish_rows()
        kept, self._kept = self._kept, ""
        failed = [venue for venue, status in statuses.items() if status.failure]
        if failed:
            said = (
                f"{venues_in_words(failed)} could not be connected. "
                "See the State column."
            )
        else:
            said = "Connected." if statuses else ""
        self._settings_view_model.set_status(f"{kept} {said}".strip(), bool(failed))

    # -- failures -----------------------------------------------------------

    def _tell_command_failed(self, cause: str, headline: str, detail: str) -> None:
        """A command the user just ran did not do what they asked (`BOT-169`): a
        message box, with the technical text behind Details…."""
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.COMMAND, cause=cause, headline=headline, detail=detail
            )
        )

    def _tell_unexpected(self, kind: str, detail: str) -> None:
        doing = {
            _ENROL: "Adding the key",
            _REMOVE: "Removing the key",
            _CHECK: "Checking the connection",
        }[kind]
        cause = {
            _ENROL: _ENROL_CAUSE,
            _REMOVE: _REMOVE_CAUSE,
            _CHECK: _CHECK_CAUSE,
        }[kind]
        self._load_from_config()
        self._tell_command_failed(
            cause, _UNEXPECTED_HEADLINE.format(doing=doing), detail
        )
