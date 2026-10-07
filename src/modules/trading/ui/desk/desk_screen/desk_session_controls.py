"""`EPIC-028K` — a desk's Emergency Stop, for the desk's own venue only.

@details Written once for every screen that stops one venue's trading
(`EPIC-021I`, `EPIC-021K`), so a screen's presenter stays a composition, and
addressed to one venue's `ITradingSession`: the Spot desk's Emergency Stop
stops Spot and nothing else (`EPIC-028B`). Its host is the desk (`EPIC-028M`
retired the single Trading screen's copy and the Dev Board's own).
`EPIC-034C` removed the Enable/Disable toggle that lived here: the order
session opens by Start bot, arm strategy or a manual order, and closes by this
stop.

Emergency Stop is never disabled and never `@safe_ui_action` (a failure must
be seen); a second click while one runs is answered in words, never sent twice.

Emergency Stop stops the venue's user-data stream in its first step, so no
event reports what its later steps did (`BUG-093`). `accountChanged` says so:
the host reads its tables again from the venue (a desk's account tabs).
A second signal once handed over the positions and orders the session
confirmed, for a host that kept its tables from events alone; that host was
the Dev Board, and the signal went with its last reader (`BOT-158`).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.session_outcome_text import (
    emergency_stop_log_lines,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.Desk")

_STOP = "emergency_stop"


class DeskSessionControls(QObject):
    """@brief Emergency-stops one venue's trading."""

    #: `(text, is_error)` — the desk's status line.
    statusChanged = Signal(str, bool)
    #: A line for the desk's log.
    logged = Signal(str)
    #: The account changed in ways no event reports: read the tables again.
    accountChanged = Signal()

    _stopped = Signal(object)

    def __init__(
        self,
        session: ITradingSession,
        thread_manager: IThreadManager,
        venue: TradingVenue,
        parent: QObject | None = None,
    ) -> None:
        """@param venue The venue `session` trades, named in this desk's log
        lines: with two desks open, a log must say which one stopped."""
        super().__init__(parent)
        self._session = session
        self._venue = venue
        self._threads = thread_manager
        self._stops: ActionOwnershipTracker[str, None, None] = ActionOwnershipTracker()
        self._stopped.connect(self._on_stopped)

    @property
    def is_open(self) -> bool:
        """Whether the venue's order session is open now."""
        return self._session.snapshot().enabled

    # -- emergency stop ---------------------------------------------------- #

    def emergency_stop(self) -> None:
        """Closes the order session, cancels every open order and closes every
        position of this venue."""
        if self._stops.active_outcome is ActionOutcome.PENDING:
            self.statusChanged.emit(
                "Emergency stop in progress — the request was already sent.", False
            )
            return
        action = self._stops.begin_action(_STOP, None, None)
        self.statusChanged.emit("Emergency stop in progress...", False)
        logger.warning("Desk emergency stop requested for %s", self._venue.value)
        self._threads.submit(self._run_stop, action.action_id)

    def _run_stop(self, action_id: int) -> None:
        try:
            self._stopped.emit((action_id, self._session.emergency_stop(), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._stopped.emit((action_id, None, str(exc)))

    def _on_stopped(self, payload: tuple) -> None:
        action_id, result, error = payload
        if not self._stops.is_current_pending(action_id, _STOP):
            self._stops.log_stale_callback("emergency_stop", action_id, _STOP)
            return
        if result is None:
            self._stops.finish_action(action_id, ActionOutcome.FAILED)
            self.statusChanged.emit(f"Error during emergency stop: {error}", True)
            self.logged.emit(f"[ERROR] Emergency stop failed: {error}")
            return
        self._report_stop(action_id, result)

    def _report_stop(self, action_id: int, result: EmergencyStopResult) -> None:
        self._stops.finish_action(
            action_id,
            ActionOutcome.SUCCEEDED if result.fully_succeeded else ActionOutcome.FAILED,
        )
        for line in emergency_stop_log_lines(result):
            self.logged.emit(line)
        if not result.final_state_confirmed:
            self.logged.emit(
                "[WARNING] Could not confirm the account after the emergency "
                "stop; the tables are read again but may lag."
            )
        self.accountChanged.emit()
        if result.fully_succeeded:
            self.statusChanged.emit("Emergency stop completed.", False)
        else:
            self.statusChanged.emit(
                "EMERGENCY STOP — PARTIALLY FAILED. See the log.", True
            )
