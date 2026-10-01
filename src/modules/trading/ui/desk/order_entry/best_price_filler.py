"""`EPIC-028O` — the order panel's BBO button: reads the book and fills a
side's price with the front of its own queue.

@details A buy gets the best bid and a sell the best ask (Binance's
"Queue 1"), so the order rests at the front of its queue and never crosses
the spread; a user who wants to cross picks Market. Reading the book is a
network call, so it runs on a worker and carries an action id from an
`ActionOwnershipTracker`: a second press supersedes the first, and the panel
switching symbol drops the read in flight (`async-ui-action-rule.md` §1).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
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

_BOOK = "book"
_QUEUE_NAME = {EntrySide.BUY: "bid", EntrySide.SELL: "ask"}


def queue_price(side: EntrySide, book: BestBidAsk) -> Decimal | None:
    """@return The front of `side`'s own queue, or `None` when that side of
    the book is empty."""
    if side is EntrySide.BUY:
        return book.bid_price if book.has_bid else None
    return book.ask_price if book.has_ask else None


class BestPriceFiller(QObject):
    """@brief Answers the view model's `bestPriceRequested` with
    `set_price_value`."""

    _book_read = Signal(object)

    def __init__(
        self,
        view_model: OrderEntryViewModel,
        terms: IOrderEntryTerms,
        thread_manager: IThreadManager,
    ) -> None:
        super().__init__(view_model)
        self._vm = view_model
        self._terms = terms
        self._threads = thread_manager
        self._reads: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._book_read.connect(self._on_book_read)
        view_model.bestPriceRequested.connect(self._on_requested)

    def drop_pending(self) -> None:
        """The panel's symbol changed: a book read still in flight is for
        the old one."""
        self._reads.invalidate_active()

    def _on_requested(self, side_value: str) -> None:
        symbol = self._vm.order_symbol
        if not symbol:
            return
        side = EntrySide(side_value)
        action = self._reads.begin_action(_BOOK, side.value, None)
        self._threads.submit(self._run_read, action.action_id, side, symbol)

    def _run_read(self, action_id: int, side: EntrySide, symbol: str) -> None:
        try:
            book = self._terms.best_bid_ask_for(symbol)
            self._book_read.emit((action_id, side, book, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._book_read.emit((action_id, side, None, str(exc)))

    def _on_book_read(self, payload: tuple) -> None:
        action_id, side, book, error = payload
        if not self._reads.is_current_pending(action_id, _BOOK):
            self._reads.log_stale_callback("_on_book_read", action_id, _BOOK)
            return
        price = queue_price(side, book) if book is not None else None
        if price is None:
            self._reads.finish_action(action_id, ActionOutcome.FAILED)
            reason = error or f"the book has no {_QUEUE_NAME[side]} yet"
            logger.warning(
                "Order panel could not read %s's book: %s",
                self._vm.order_symbol,
                reason,
            )
            self._vm.show_result(
                f"Could not read the best price: {reason}", is_error=True
            )
            return
        self._reads.finish_action(action_id, ActionOutcome.SUCCEEDED)
        logger.debug(
            "Order panel %s price set to the best %s %s",
            side.value,
            _QUEUE_NAME[side],
            price,
        )
        self._vm.set_price_value(side, price)
