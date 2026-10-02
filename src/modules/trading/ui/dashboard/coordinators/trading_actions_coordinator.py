"""`BOT-144` — the Dev Board's per-order cancel, pulled out of
`DashboardPresenter`.

@details It used to hold four action families. Enable/Disable and Emergency
Stop left for the desks' shared `DeskSessionControls`, and the manual order
for the desks' order panel behind F9 (both `EPIC-028M`); the Open orders
table's per-row cancel is what remains.

Shape-matches this screen's other Coordinators: a plain class, narrow
constructor-injected callables rather than the whole Presenter, no FSM state
and no action-id bookkeeping (`async-ui-action-rule.md` §2). The completion
handler stays on `DashboardPresenter`, which owns the order book it updates.

No tracker, on purpose: cancelling order A and cancelling order B on another
row are independent actions, and fencing them through one tracker would let
the second row's cancel invalidate the first's.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
        IOrderSubmission,
    )
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class TradingActionsCoordinator:
    """Cancels one open order off the UI thread and reports the outcome."""

    def __init__(
        self,
        thread_manager: IThreadManager,
        order_submission: IOrderSubmission,
        emit_cancel_completed: Callable[[tuple], None],
        append_log: Callable[[str], None],
    ) -> None:
        """@param emit_cancel_completed Bound to the presenter's queued
        signal: `(symbol, client_order_id, CancelOrderResult | None,
        error_message | None)`."""
        self._thread_manager = thread_manager
        self._order_submission = order_submission
        self._emit_cancel_completed = emit_cancel_completed
        self._append_log = append_log

    def request_cancel_order(self, symbol: str, client_order_id: str) -> None:
        self._append_log(f"Cancelling order {client_order_id} ({symbol})...")
        self._thread_manager.submit(self.run_cancel_order, symbol, client_order_id)

    def run_cancel_order(self, symbol: str, client_order_id: str) -> None:
        try:
            result = self._order_submission.cancel(symbol, client_order_id)
            self._emit_cancel_completed((symbol, client_order_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._emit_cancel_completed((symbol, client_order_id, None, str(exc)))
