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
row the user clicked may be a fill out of date. It closes only if the read
is still the position confirmed (`close_mismatch`): not turned to the other
side, not grown past the size shown.

One action at a time; a click while one runs is answered in words, never
queued (`async-ui-action-rule.md` §1).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.failure_cause import (
    failure_cause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    ConfirmedClose,
    close_mismatch,
    market_close_order_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_failure import (
    submit_failure_notice,
    submit_failure_of,
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
        self,
        ports: VenueTradingPorts,
        thread_manager: IThreadManager,
        notifier: INotifier,
    ) -> None:
        super().__init__()
        self._notifier = notifier
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

    def close_position(self, confirmed: ConfirmedClose) -> None:
        self._start(f"close {confirmed.symbol}", self._run_close, confirmed)

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
        unsent: list[str] = []
        details: list[str] = []
        refusal: str | None = None
        for symbol, client_order_id in orders:
            try:
                result = self._ports.order_submission.cancel(symbol, client_order_id)
            except Exception as exc:  # noqa: BLE001 - worker boundary: one refused cancel must not hide the others' outcome
                unsent.append(f"{symbol} {client_order_id}")
                details.append(f"{symbol} {client_order_id}: {failure_detail(exc)}")
                continue
            if result.blocked_by is not None:
                refusal = format_execute_order_block_reason(result.blocked_by)
                break
            cancelled += 1
            self._cancelled.emit(client_order_id)
        text = _cancel_text(cancelled, len(orders), unsent, refusal)
        failed = bool(unsent) or refusal is not None
        notice = (
            self._command_notice("cancel", text, "; ".join(details)) if failed else None
        )
        self._done.emit(_Outcome(action_id, text, failed, None, notice))

    def _run_close(self, action_id: int, confirmed: ConfirmedClose) -> None:
        symbol = confirmed.symbol
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
                self._refused(action_id, f"No open {symbol} position to close.")
                return
            mismatch = close_mismatch(confirmed, position)
            if mismatch is not None:
                self._refused(action_id, mismatch)
                return
            result = self._ports.order_submission.submit(
                market_close_order_for(position), live=True
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary
            failure = submit_failure_of(exc)
            notice = submit_failure_notice(
                failure, venue=self._ports.venue, area="close", what="close order"
            )
            self._done.emit(_Outcome(action_id, notice.headline, True, None, notice))
            return
        if result.blocked:
            self._refused(
                action_id, format_execute_order_block_reason(result.blocked_by)
            )
            return
        text = f"Close order sent for {symbol}."
        self._done.emit(_Outcome(action_id, text, False, symbol, None))

    def _refused(self, action_id: int, text: str) -> None:
        """A refusal with its own authored message: no exception behind it."""
        notice = self._command_notice("close.refused", text)
        self._done.emit(_Outcome(action_id, text, True, None, notice))

    def _command_notice(
        self, what: str, headline: str, detail: str = ""
    ) -> FailureNotice:
        return FailureNotice(
            FailureKind.COMMAND,
            failure_cause(self._ports.venue, what),
            headline,
            detail=detail,
        )

    # -- UI thread ----------------------------------------------------- #

    def _on_done(self, outcome: _Outcome) -> None:
        action_id = outcome.action_id
        if not self._actions.is_current_pending(action_id, _ACTION):
            self._actions.log_stale_callback("_on_done", action_id, _ACTION)
            return
        self._actions.finish_action(
            action_id,
            ActionOutcome.FAILED if outcome.failed else ActionOutcome.SUCCEEDED,
        )
        logger.info("Account tabs on %s: %s", self._ports.venue.value, outcome.text)
        if outcome.notice is not None:
            if outcome.notice.detail:
                logger.warning(
                    "Account tabs on %s failed: %s",
                    self._ports.venue.value,
                    outcome.notice.detail,
                )
            self._notifier.report_failure(outcome.notice)
        self.finished.emit(outcome.text, outcome.failed)
        if outcome.closed_symbol is not None:
            self.positionCloseSent.emit(outcome.closed_symbol)


@dataclass(frozen=True)
class _Outcome:
    """What a worker hands the UI thread: the words for the status line, and
    the notice when the action failed or was refused (`BOT-169`)."""

    action_id: int
    text: str
    failed: bool
    closed_symbol: str | None
    notice: FailureNotice | None


def _cancel_text(
    cancelled: int, asked: int, unsent: list[str], refusal: str | None
) -> str:
    if asked == 1 and not unsent and refusal is None:
        return "Order cancelled."
    text = f"Cancelled {cancelled} of {asked} orders."
    if unsent:
        text += (
            f" Could not cancel: {', '.join(unsent)}. Check Open orders and try again."
        )
    if refusal is not None:
        text += f" {refusal}"
    return text
