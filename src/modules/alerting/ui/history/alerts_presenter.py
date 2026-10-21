"""The Alerts screen's presenter (`EPIC-036D2`, and the status-bar indicator of `EPIC-036D3`).

It reads the history through `IAlertHistory` on the thread pool and hands the report to the
view on the UI thread: the read opens the outbox's database, which must not block a paint.
It reads the whole list when its mode is shown and Refresh asks now. A `QTimer` reads in the
background every `REFRESH_INTERVAL_MS` whether or not the mode is visible, because the
status-bar indicator the view offers is there in every mode; a hidden mode reads only the few
newest alert (`HEALTH_LIMIT`), whose read also carries every channel's own state, and it
updates the indicator only: the list on screen is not replaced by a one-row one. A click on the indicator shows the mode. One read is in
flight at a time, so a slow disk is never queued behind itself. An answer for a read that
is no longer the current one is dropped, and none arrives after `shutdown()`
(`async-ui-action-rule.md`).

A failed read leaves the last list on screen and says so in words, and the indicator says
`unknown` rather than keep a state nobody has checked anymore; the exception is told by its
type name only, as on the Options page. The warning is logged once per run of failures, not
every 15 s.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Slot
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_history import (
    IAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history import history_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_view import (
    ALERTS_ROUTE,
    AlertsView,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_action_relay import (
    AlertsActionRelay,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import INavigationService
from sagittarius_engine.extensions.pyside_mvc import (
    BasePresenter,
    BaseView,
    safe_ui_action,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Alerting.History")

#: How many alerts one read returns while the mode is shown.
HISTORY_LIMIT = 500
#: And while it is hidden: only the status-bar indicator reads then; a channel's health is its
#: own newest delivery whatever the window (`IOutbox.latest_real_delivery`), so one row is enough.
HEALTH_LIMIT = 1
#: The first background read after start, so the indicator appears soon without a read at build
#: (every mode is built at start; a read then started pool threads the window does not own).
FIRST_READ_MS = 5_000
#: How often the screen asks again, in milliseconds.
REFRESH_INTERVAL_MS = 15_000
_READ = "read"


class AlertsPresenter(BasePresenter):
    """@brief Reads the alert history off the UI thread and shows it."""

    def __init__(self, view: AlertsView, container: IContainer) -> None:
        super().__init__(view, container)
        self._view = view
        self._container = container
        self._history: IAlertHistory = container.resolve(IAlertHistory)
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )
        self._relay = AlertsActionRelay(self._on_read_done)
        self._reading = False
        self._reading_full = False
        self._full_read_wanted = False
        self._failing = False
        view.refresh_button.clicked.connect(self.refresh)
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._first_read = QTimer(self)
        self._first_read.setSingleShot(True)
        self._first_read.setInterval(FIRST_READ_MS)
        self._first_read.timeout.connect(self._poll)
        self._first_read.start()
        view.indicator_clicked.connect(self._show_the_mode)
        logger.info(
            "Alerts screen: reads up to %d alert(s) when shown and %d while hidden (for the "
            "status-bar indicator), first after %d ms, then every %d ms.",
            HISTORY_LIMIT,
            HEALTH_LIMIT,
            FIRST_READ_MS,
            REFRESH_INTERVAL_MS,
        )

    def on_mode_shown(self, source: NavigationSource) -> None:
        """The mode is built at start with every other, so nothing is read until the owner can
        see it: it reads the whole list now."""
        self.refresh()

    def _poll(self) -> None:
        """The background read: the whole list while the mode is visible, the few newest alerts
        (enough for the indicator) while it is not. Silent either way."""
        self._start_read(HISTORY_LIMIT if self._view.isVisible() else HEALTH_LIMIT)

    def _show_the_mode(self) -> None:
        """The indicator was clicked. The navigation service is the window's and exists only
        once the window is built, so it is asked for now, not at construction."""
        navigation: INavigationService = self._container.resolve(INavigationService)
        navigation.navigate(ALERTS_ROUTE, source=NavigationSource.USER_INTENT)

    @Slot()
    @safe_ui_action
    def refresh(self) -> None:
        """A read the owner asked for (Refresh, or the mode shown): says it is reading and
        greys the button. The timer's reads are silent, so the list does not jump every 15 s."""
        self._view.refresh_button.setEnabled(False)
        self._view.show_history_note(history_words.READING)
        if self._reading and not self._reading_full:
            self._full_read_wanted = (
                True  # the read out is the indicator's: the list follows it
            )
            return
        self._start_read(HISTORY_LIMIT)

    def _start_read(self, limit: int) -> None:
        """Asks for a fresh read unless one is already out."""
        if self._reading:
            return
        self._reading = True
        self._reading_full = limit == HISTORY_LIMIT
        action = self._tracker.begin_action(_READ, None, None)
        try:
            self._thread_manager.submit(
                self._read_history_on_pool, action.action_id, limit
            )
        except Exception:
            self._reading = False
            self._view.refresh_button.setEnabled(True)
            raise

    def shutdown(self) -> None:
        """Answers still in flight are dropped, and none is delivered after this."""
        self._timer.stop()
        self._first_read.stop()
        self._tracker.invalidate_active()
        self._relay.stop_delivering()
        super().shutdown()

    def _read_history_on_pool(self, action_id: int, limit: int) -> None:
        """Runs on the thread pool: touches no widget; reports through the relay."""
        try:
            report = self._history.read(limit)
        except Exception as exc:  # noqa: BLE001 - worker boundary: told in words, not lost to a pool thread
            self._relay.hand_over((action_id, None, type(exc).__name__))
        else:
            self._relay.hand_over((action_id, report, None))

    def _on_read_done(self, payload: tuple) -> None:
        """Runs on the UI thread."""
        action_id, report, error_type = payload
        if not self._tracker.is_current_pending(action_id, _READ):
            self._tracker.log_stale_callback(_READ, action_id, _READ)
            return
        self._reading = False
        full = self._reading_full
        if error_type is not None:
            self._tracker.finish_action(action_id, ActionOutcome.FAILED)
            self._show_read_failed(error_type)
        else:
            self._tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
            self._failing = False
            if full:
                self._view.show_history_note("")
                self._view.show_alert_history(report.rows, report.channels)
            else:
                self._view.show_channel_health(report.channels)
        if self._full_read_wanted:
            self._full_read_wanted = False
            self._start_read(HISTORY_LIMIT)
        else:
            self._view.refresh_button.setEnabled(True)

    def _show_read_failed(self, error_type: str) -> None:
        if not self._failing:
            logger.warning("Alerts screen: the history read raised %s", error_type)
        self._failing = True
        self._view.show_health_unknown(error_type)
        self._view.show_history_note(
            history_words.READ_FAILED.format(error_type=error_type)
        )


def build_alerts_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    """The presenter factory the screen contribution names."""
    if not isinstance(view, AlertsView):
        raise TypeError(
            f"the Alerts screen's presenter was handed a {type(view).__name__}, "
            "not an AlertsView"
        )
    return AlertsPresenter(view, container)
