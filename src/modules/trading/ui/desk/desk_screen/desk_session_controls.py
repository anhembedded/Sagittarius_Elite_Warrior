"""`EPIC-028K` — a desk's Enable/Disable toggle and its Emergency Stop, for
the desk's own venue only.

@details Written once for every screen that turns one venue's trading on and
off (`EPIC-021I`, `EPIC-021K`), so a screen's presenter stays a composition,
and addressed to one venue's `ITradingSession`: the Spot desk's Emergency Stop
stops Spot and nothing else (`EPIC-028B`). Its two hosts are the desks and the
Dev Board (`EPIC-028M`, which retired the single Trading screen's copy and the
Dev Board's own).

Two trackers, never one (`BUG-089`): an `ActionOwnershipTracker` holds one
active action whatever its kind, so a toggle click landing while Emergency
Stop runs would otherwise fence the stop's own result as stale. Emergency
Stop is never disabled and never `@safe_ui_action` (a failure must be seen);
a second click while one runs is answered in words, never sent twice.

Emergency Stop stops the venue's user-data stream in its first step, so no
event reports what its later steps did (`BUG-093`). Two signals say so, one
per kind of host: `accountChanged` asks a host to read its tables again (a
desk's account tabs read the venue), and `accountReconciled` hands over the
positions and open orders the session itself confirmed, for a host that
keeps its tables from events and these answers alone (the Dev Board). An
unconfirmed final state hands over nothing, and nor does an enable refused
before the venue was read: an empty answer from a failed or skipped read is
not "flat".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.ui.session_outcome_text import (
    ENABLE_BLOCK_MESSAGES,
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

_TOGGLE = "toggle_trading"
_STOP = "emergency_stop"


@dataclass(frozen=True)
class ReconciledAccount:
    """What the venue holds, as the session confirmed it in an enable or an
    Emergency Stop."""

    positions: tuple[LivePosition, ...]
    open_orders: tuple[Order, ...]


class DeskSessionControls(QObject):
    """@brief Enables, disables and emergency-stops one venue's trading."""

    #: `(enabled, busy)` — the toggle's state to show.
    stateChanged = Signal(bool, bool)
    #: `(text, is_error)` — the desk's status line.
    statusChanged = Signal(str, bool)
    #: A line for the desk's log.
    logged = Signal(str)
    #: Trading was just enabled: the desk's chart goes live (`BUG-107`).
    tradingEnabled = Signal()
    #: The account changed in ways no event reports: read the tables again.
    accountChanged = Signal()
    #: A `ReconciledAccount` the session confirmed: the tables' new content.
    accountReconciled = Signal(object)

    _enabled = Signal(object)
    _disabled = Signal(object)
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
        self._toggles: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )
        self._stops: ActionOwnershipTracker[str, None, None] = ActionOwnershipTracker()
        self._enabled.connect(self._on_enabled)
        self._disabled.connect(self._on_disabled)
        self._stopped.connect(self._on_stopped)

    @property
    def is_enabled(self) -> bool:
        return self._session.snapshot().enabled

    # -- toggle --------------------------------------------------------- #

    def toggle(self) -> None:
        """Enables trading when it is off, disables it when it is on."""
        if self._stops.active_outcome is ActionOutcome.PENDING:
            self.statusChanged.emit(
                "Emergency stop in progress — wait for it to finish before "
                "enabling or disabling trading.",
                True,
            )
            return
        action = self._toggles.begin_action(_TOGGLE, None, None)
        enabled = self.is_enabled
        self.stateChanged.emit(enabled, True)
        task = self._run_disable if enabled else self._run_enable
        self._threads.submit(task, action.action_id)

    def _run_enable(self, action_id: int) -> None:
        try:
            self._enabled.emit((action_id, self._session.enable(), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._enabled.emit((action_id, None, str(exc)))

    def _run_disable(self, action_id: int) -> None:
        try:
            self._session.disable()
            self._disabled.emit((action_id, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._disabled.emit((action_id, str(exc)))

    def _on_enabled(self, payload: tuple) -> None:
        action_id, result, error = payload
        if not self._finish_toggle(action_id, failed=result is None):
            return
        if result is None:
            self.statusChanged.emit(f"Error enabling trading: {error}", True)
            return
        self._show_enable_result(result)

    def _show_enable_result(self, result: EnableTradingResult) -> None:
        self.stateChanged.emit(result.enabled, False)
        if result.account_was_read:
            self.accountReconciled.emit(
                ReconciledAccount(
                    result.reconciled_positions, result.reconciled_open_orders
                )
            )
        if result.enabled:
            self.statusChanged.emit("Trading enabled.", False)
            self.tradingEnabled.emit()
        elif result.block_reason is not None:
            self.statusChanged.emit(ENABLE_BLOCK_MESSAGES[result.block_reason], True)
        self.accountChanged.emit()

    def _on_disabled(self, payload: tuple) -> None:
        action_id, error = payload
        if not self._finish_toggle(action_id, failed=error is not None):
            return
        if error is not None:
            self.statusChanged.emit(f"Error disabling trading: {error}", True)
            return
        self.stateChanged.emit(False, False)
        self.statusChanged.emit("Trading disabled.", False)

    def _finish_toggle(self, action_id: int, *, failed: bool) -> bool:
        """Records the toggle's outcome; `False` for a superseded answer."""
        if not self._toggles.is_current_pending(action_id, _TOGGLE):
            self._toggles.log_stale_callback("toggle_trading", action_id, _TOGGLE)
            return False
        self._toggles.finish_action(
            action_id, ActionOutcome.FAILED if failed else ActionOutcome.SUCCEEDED
        )
        if failed:
            self.stateChanged.emit(self.is_enabled, False)
        return True

    # -- emergency stop ---------------------------------------------------- #

    def emergency_stop(self) -> None:
        """Disables trading, cancels every open order and closes every
        position of this venue."""
        if self._stops.active_outcome is ActionOutcome.PENDING:
            self.statusChanged.emit(
                "Emergency stop in progress — the request was already sent.", False
            )
            return
        action = self._stops.begin_action(_STOP, None, None)
        self.stateChanged.emit(self.is_enabled, True)
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
            self.stateChanged.emit(self.is_enabled, False)
            self.statusChanged.emit(f"Error during emergency stop: {error}", True)
            self.logged.emit(f"[ERROR] Emergency stop failed: {error}")
            return
        self._report_stop(action_id, result)

    def _report_stop(self, action_id: int, result: EmergencyStopResult) -> None:
        self._stops.finish_action(
            action_id,
            ActionOutcome.SUCCEEDED if result.fully_succeeded else ActionOutcome.FAILED,
        )
        self.stateChanged.emit(self.is_enabled, False)
        for line in emergency_stop_log_lines(result):
            self.logged.emit(line)
        if result.final_state_confirmed:
            self.accountReconciled.emit(
                ReconciledAccount(result.final_positions, result.final_open_orders)
            )
        else:
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
