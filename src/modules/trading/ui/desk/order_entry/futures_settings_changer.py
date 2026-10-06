"""`EPIC-028I` — sends the panel's margin-mode and leverage chips to the
exchange and reports its answer.

@details The chip asks (`OrderOptionsViewModel`'s request signals); this
sends `EPIC-028F`'s command through the desk's own `IFuturesSettingsControl`
on a worker, says what the exchange confirmed or why it refused (an open
position, a safety gate, the exchange's code), and asks the panel to read
the symbol again so the chips show the exchange's setting, not the request.
One change at a time; an answer for a symbol the panel has left is dropped
(`async-ui-action-rule.md` §1): the change is finished, but neither shown
on the new symbol's panel nor followed by a read of it. Every message names
its symbol.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_settings_control import (
    IFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.OrderEntry")

_CHANGE = "settings"


class FuturesSettingsChanger(QObject):
    """@brief The panel's margin-mode and leverage changes."""

    _answered = Signal(object)

    def __init__(
        self,
        view_model: OrderEntryViewModel,
        control: IFuturesSettingsControl,
        thread_manager: IThreadManager,
        reread: Callable[[], None],
    ) -> None:
        super().__init__(view_model)
        self._vm = view_model
        self._writes = view_model.presenter_side()
        self._control = control
        self._threads = thread_manager
        self._reread = reread
        self._changes: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._answered.connect(self._on_answered)
        view_model.options.marginTypeRequested.connect(self._change_margin_type)
        view_model.options.leverageRequested.connect(self._change_leverage)

    def _change_margin_type(self, margin_type: MarginType) -> None:
        symbol = self._vm.order_symbol
        self._start(
            symbol,
            f"margin mode {margin_type.value}",
            lambda: self._control.change_margin_type(symbol, margin_type),
        )

    def _change_leverage(self, leverage: int) -> None:
        symbol = self._vm.order_symbol
        self._start(
            symbol,
            f"leverage {leverage}x",
            lambda: self._control.change_leverage(symbol, leverage),
        )

    def _start(
        self, symbol: str, what: str, send: Callable[[], AccountControlResult]
    ) -> None:
        if not symbol:
            return
        if self._changes.active_outcome is ActionOutcome.PENDING:
            self._writes.show_result("A change is already being sent.", is_error=True)
            return
        action = self._changes.begin_action(_CHANGE, symbol, None)
        self._writes.set_busy(True, f"Setting {what} on {symbol}...")
        logger.info("Order panel asks for %s on %s", what, symbol)
        self._threads.submit(self._run, action.action_id, symbol, what, send)

    def _run(
        self,
        action_id: int,
        symbol: str,
        what: str,
        send: Callable[[], AccountControlResult],
    ) -> None:
        what = f"{what} on {symbol}"
        try:
            self._answered.emit((action_id, symbol, what, send(), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._answered.emit((action_id, symbol, what, None, str(exc)))

    def _on_answered(self, payload: tuple) -> None:
        action_id, symbol, what, result, error = payload
        if not self._changes.is_current_pending(action_id, _CHANGE):
            self._changes.log_stale_callback("_on_answered", action_id, _CHANGE)
            return
        text, failed = _outcome(what, result, error)
        self._changes.finish_action(
            action_id, ActionOutcome.FAILED if failed else ActionOutcome.SUCCEEDED
        )
        logger.info("Order panel %s: %s", what, text)
        if symbol != self._vm.order_symbol:
            logger.info("Order panel left %s before its answer; not shown", symbol)
            return
        self._writes.show_result(text, is_error=failed)
        self._reread()


def _outcome(
    what: str, result: AccountControlResult | None, error: str | None
) -> tuple[str, bool]:
    if result is None:
        return f"Could not set {what}: {error}", True
    if result.blocked_by is not None:
        reason = result.detail or result.blocked_by.value.replace("_", " ")
        return f"The exchange did not set {what}: {reason}", True
    return f"Set {what}.", False
