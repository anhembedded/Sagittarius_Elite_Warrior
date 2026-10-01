"""`EPIC-028J` — keeps one desk's summary panel current.

@details Read once when the desk opens (`IAccountActivity.summary`), since
`AccountSummaryRefreshService` publishes only while the venue's trading is
on and only on change; then kept by the venue's own events through its
`OrderFeed`: `AccountSummaryChangedEvent` replaces the figures and clears
the stale mark, `AccountSummaryStaleEvent` sets it with its reason
(`EPIC-028Q`). A fill needs nothing here: the refresh service re-reads the
account after every fill and publishes the change.

An open read that answers after a newer event is dropped: the event is the
later truth (`async-ui-action-rule.md` §1).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_changed_event import (
    AccountSummaryChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_stale_event import (
    AccountSummaryStaleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.account_summary_panel import (
    AccountSummaryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.summary_lines import (
    summary_lines_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.AccountSummary")

_READ = "read"
_UNREAD_REASON = "the account could not be read"


class AccountSummaryPresenter(QObject):
    """@brief One desk's summary figures, read once and then kept."""

    _read = Signal(object)

    def __init__(
        self,
        view: AccountSummaryPanel,
        activity: IAccountActivity,
        feed: OrderFeed,
        thread_manager: IThreadManager,
    ) -> None:
        super().__init__(view)
        self._view = view
        self._activity = activity
        self._threads = thread_manager
        self._reads: ActionOwnershipTracker[str, None, None] = ActionOwnershipTracker()
        self._read.connect(self._on_read)
        feed.accountSummaryChanged.connect(self._on_changed)
        feed.accountSummaryStale.connect(self._on_stale)

    def refresh(self) -> None:
        action = self._reads.begin_action(_READ, None, None)
        self._threads.submit(self._run_read, action.action_id)

    def _run_read(self, action_id: int) -> None:
        try:
            self._read.emit((action_id, self._activity.summary(), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._read.emit((action_id, None, str(exc)))

    def _on_read(self, payload: tuple) -> None:
        action_id, summary, error = payload
        if not self._reads.is_current_pending(action_id, _READ):
            self._reads.log_stale_callback("_on_read", action_id, _READ)
            return
        if summary is None:
            self._reads.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning("Account summary could not be read: %s", error)
            self._view.mark_stale(error or _UNREAD_REASON)
            return
        self._reads.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._show(summary)

    def _on_changed(self, event: AccountSummaryChangedEvent) -> None:
        self._reads.invalidate_active()
        self._show(event.summary)

    def _on_stale(self, event: AccountSummaryStaleEvent) -> None:
        self._reads.invalidate_active()
        logger.info(
            "Account summary on %s is stale: %s", event.venue.value, event.reason
        )
        self._view.mark_stale(event.reason)

    def _show(self, summary: AccountSummary) -> None:
        self._view.set_lines(summary_lines_for(summary))
        self._view.clear_stale()
