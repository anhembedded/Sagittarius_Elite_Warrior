"""The Alerts screen's presenter (`EPIC-036D2`).

It reads the history through `IAlertHistory` on the thread pool and hands the report to the
view on the UI thread: the read opens the outbox's database, which must not block a paint.
A `QTimer` asks again every `REFRESH_INTERVAL_MS`, and Refresh asks now; one read is in
flight at a time, so a slow disk is never queued behind itself. An answer for a read that
is no longer the current one is dropped, and none arrives after `shutdown()`
(`async-ui-action-rule.md`).

A failed read leaves the last list on screen and says so in words; the exception is told by
its type name only, as on the Options page.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Slot
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_history import (
    IAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history import history_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_view import (
    AlertsView,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_action_relay import (
    AlertsActionRelay,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.extensions.pyside_mvc import (
    BasePresenter,
    BaseView,
    safe_ui_action,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Alerting.History")

#: How many alerts one read returns.
HISTORY_LIMIT = 500
#: How often the screen asks again, in milliseconds.
REFRESH_INTERVAL_MS = 15_000
_READ = "read"


class AlertsPresenter(BasePresenter):
    """@brief Reads the alert history off the UI thread and shows it."""

    def __init__(self, view: AlertsView, container: IContainer) -> None:
        super().__init__(view, container)
        self._view = view
        self._history: IAlertHistory = container.resolve(IAlertHistory)
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )
        self._relay = AlertsActionRelay(self._on_read_done)
        self._reading = False
        view.refresh_button.clicked.connect(self.refresh)
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        logger.info(
            "Alerts screen: reading up to %d alert(s), again every %d ms.",
            HISTORY_LIMIT,
            REFRESH_INTERVAL_MS,
        )
        self.refresh()

    @Slot()
    @safe_ui_action
    def refresh(self) -> None:
        """Asks for a fresh read unless one is already out."""
        if self._reading:
            return
        self._reading = True
        action = self._tracker.begin_action(_READ, None, None)
        self._view.refresh_button.setEnabled(False)
        self._view.show_history_note(history_words.READING)
        self._thread_manager.submit(self._read_history_on_pool, action.action_id)

    def shutdown(self) -> None:
        """Answers still in flight are dropped, and none is delivered after this."""
        self._timer.stop()
        self._tracker.invalidate_active()
        self._relay.stop_delivering()
        super().shutdown()

    def _read_history_on_pool(self, action_id: int) -> None:
        """Runs on the thread pool: touches no widget; reports through the relay."""
        try:
            report = self._history.read(HISTORY_LIMIT)
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
        self._view.refresh_button.setEnabled(True)
        if error_type is not None:
            self._tracker.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning("Alerts screen: the history read raised %s", error_type)
            self._view.show_history_note(
                history_words.READ_FAILED.format(error_type=error_type)
            )
            return
        self._tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._view.show_history_note("")
        self._view.show_alert_history(report.rows, report.channels)


def build_alerts_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    """The presenter factory the screen contribution names."""
    if not isinstance(view, AlertsView):
        raise TypeError(
            f"the Alerts screen's presenter was handed a {type(view).__name__}, "
            "not an AlertsView"
        )
    return AlertsPresenter(view, container)
