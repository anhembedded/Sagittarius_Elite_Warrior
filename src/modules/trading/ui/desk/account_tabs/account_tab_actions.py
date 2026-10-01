"""`EPIC-028J` — what a desk's account tabs do at the exchange: cancel one
order, cancel every order shown, close a position at market.

@details Every action goes through the desk's own venue's
`IOrderSubmission`, so the trading switch, the connection gate and the app's
limits apply exactly as they do to the order panel. The confirmation was
asked before the request reached here (`AccountTabsPanel`).

**Cancel all is one cancel per order shown**, not the venue's cancel-all
endpoint: it cancels what the user saw and confirmed, on every symbol the
tab showed, and a refusal names the order it concerns. A safety-gate
refusal (trading off, no connection) stops the rest, since it would refuse
each one the same way.

**Close reads the position again first** (`market_close_order_for`): the
row the user clicked may be a fill out of date.

One action at a time; a click while one runs is answered in words, never
queued (`async-ui-action-rule.md` §1).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    market_close_order_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.AccountTabs")

_ACTION = "account_action"


class AccountTabActions(QObject):
    """@brief Runs the tabs' exchange actions off the UI thread."""

    #: The client order id of an order the venue confirmed cancelled.
    orderCancelled = Signal(str)
    #: The outcome of an action, in words, and whether it failed.
    finished = Signal(str, bool)
    #: A close order was placed; the positions are worth reading again.
    positionCloseSent = Signal(str)

    _cancelled = Signal(str)
    _done = Signal(object)

    def __init__(
        self, ports: VenueTradingPorts, thread_manager: IThreadManager
    ) -> None:
        super().__init__()
        self._ports = ports
        self._threads = thread_manager
        self._actions: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._cancelled.connect(self.orderCancelled)
        self._done.connect(self._on_done)

    def cancel_one(self, symbol: str, client_order_id: str) -> None:
        self._start(
            f"cancel {client_order_id}", self._run_cancel, ((symbol, client_order_id),)
        )

    def cancel_all(self, rows: Sequence[OpenOrderRow]) -> None:
        orders = tuple((row.symbol, row.client_order_id) for row in rows)
        self._start(f"cancel {len(orders)} orders", self._run_cancel, orders)

    def close_position(self, symbol: str) -> None:
        self._start(f"close {symbol}", self._run_close, symbol)

    def _start[T](
        self, label: str, task: Callable[[int, T], None], argument: T
    ) -> None:
        if self._actions.active_outcome is ActionOutcome.PENDING:
            self.finished.emit("Another action is still running.", True)
            return
        action = self._actions.begin_action(_ACTION, label, None)
        logger.info("Account tabs on %s: %s", self._ports.venue.value, label)
        self._threads.submit(task, action.action_id, argument)

    # -- workers ------------------------------------------------------- #

    def _run_cancel(self, action_id: int, orders: tuple[tuple[str, str], ...]) -> None:
        cancelled = 0
        failures: list[str] = []
        for symbol, client_order_id in orders:
            try:
                result = self._ports.order_submission.cancel(symbol, client_order_id)
            except Exception as exc:  # noqa: BLE001 - worker boundary: one refused cancel must not hide the others' outcome
                failures.append(f"{symbol} {client_order_id}: {exc}")
                continue
            if result.blocked_by is not None:
                failures.append(format_execute_order_block_reason(result.blocked_by))
                break
            cancelled += 1
            self._cancelled.emit(client_order_id)
        self._done.emit(
            (
                action_id,
                _cancel_text(cancelled, len(orders), failures),
                bool(failures),
                None,
            )
        )

    def _run_close(self, action_id: int, symbol: str) -> None:
        try:
            position = next(
                (
                    p
                    for p in self._ports.account_snapshot.open_positions()
                    if p.symbol == symbol
                ),
                None,
            )
            if position is None:
                self._done.emit(
                    (action_id, f"No open {symbol} position to close.", True, None)
                )
                return
            result = self._ports.order_submission.submit(
                market_close_order_for(position), live=True
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self._done.emit((action_id, f"The close failed: {exc}", True, None))
            return
        if result.blocked:
            text = format_execute_order_block_reason(result.blocked_by)
            self._done.emit((action_id, text, True, None))
            return
        self._done.emit((action_id, f"Close order sent for {symbol}.", False, symbol))

    # -- UI thread ----------------------------------------------------- #

    def _on_done(self, payload: tuple) -> None:
        action_id, text, failed, closed_symbol = payload
        if not self._actions.is_current_pending(action_id, _ACTION):
            self._actions.log_stale_callback("_on_done", action_id, _ACTION)
            return
        self._actions.finish_action(
            action_id, ActionOutcome.FAILED if failed else ActionOutcome.SUCCEEDED
        )
        logger.info("Account tabs on %s: %s", self._ports.venue.value, text)
        self.finished.emit(text, failed)
        if closed_symbol is not None:
            self.positionCloseSent.emit(closed_symbol)


def _cancel_text(cancelled: int, asked: int, failures: list[str]) -> str:
    if asked == 1 and not failures:
        return "Order cancelled."
    head = f"Cancelled {cancelled} of {asked} orders."
    return head if not failures else f"{head} {'; '.join(failures)}"
