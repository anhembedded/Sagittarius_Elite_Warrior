"""`EPIC-028J` — reads the pages a desk's two history tabs show.

@details **`since` is fixed while paging.** A desk's history starts at a
`since` set when it is (re)opened — the desk opening, its symbol changing,
"hide other pairs" flipping, the user asking for a refresh — and every page
click reuses it. `CachedAccountHistoryReader` serves a repeated span from
its cache only for the same or a later `since` (`EPIC-028Q`), so a `since`
taken afresh on each click would re-read the exchange on every page and
spend Binance's request weight for nothing.

**A fill re-reads the pages shown**, with the same `since`, so a new order
or fill appears; the cache makes it at most `HISTORY_CACHE_TTL` late.

Each read runs on a worker and carries an action id per history; an answer
for a superseded read is logged and dropped (`async-ui-action-rule.md` §1).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_rows import (
    build_order_history_row,
    build_trade_history_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
    HistoryView,
    history_view_for,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.AccountTabs")

#: ADR O5: a desk's history tabs show the last seven days.
DESK_HISTORY_SPAN = timedelta(days=7)

type Clock = Callable[[], datetime]


class HistoryDisplay(Protocol):
    """Where the loader's pages go; `AccountTabsPanel` in the app. A
    `Protocol` because the implementer is a `QObject` (`architecture-rule.md`
    §2.1 reason (a))."""

    def show_history(self, kind: HistoryKind, view: HistoryView[object]) -> None: ...

    def show_history_loading(self, kind: HistoryKind) -> None: ...

    def show_history_error(self, kind: HistoryKind, text: str) -> None: ...


class HistoryTabsLoader(QObject):
    """@brief Both history tabs' current page, read off the UI thread."""

    _read = Signal(object)

    def __init__(
        self,
        display: HistoryDisplay,
        activity: IAccountActivity,
        thread_manager: IThreadManager,
        clock: Clock,
    ) -> None:
        super().__init__()
        self._display = display
        self._activity = activity
        self._threads = thread_manager
        self._clock = clock
        self._requests: dict[HistoryKind, HistoryRequest] = {}
        self._reads: dict[HistoryKind, ActionOwnershipTracker[str, int, None]] = {
            kind: ActionOwnershipTracker() for kind in HistoryKind
        }
        self._read.connect(self._on_read)

    def open(self, symbol: str | None) -> None:
        """Starts both histories over: a new `since`, page one.
        @param symbol One pair, or `None` for every active pair."""
        since = self._clock() - DESK_HISTORY_SPAN
        for kind in HistoryKind:
            self._load(kind, HistoryRequest(symbol=symbol, since=since))

    def turn_to(self, kind: HistoryKind, page: int) -> None:
        """Shows another page of `kind`, over the same span."""
        current = self._requests.get(kind)
        if current is None or page < 0:
            return
        self._load(kind, current.at_page(page))

    def reread(self) -> None:
        """Reads the pages shown again, over the same span (after a fill)."""
        for kind, request in list(self._requests.items()):
            self._load(kind, request)

    def request_for(self, kind: HistoryKind) -> HistoryRequest | None:
        return self._requests.get(kind)

    def _load(self, kind: HistoryKind, request: HistoryRequest) -> None:
        self._requests[kind] = request
        action = self._reads[kind].begin_action(kind.value, request.page, None)
        self._display.show_history_loading(kind)
        self._threads.submit(self._run_read, action.action_id, kind, request)

    def _run_read(
        self, action_id: int, kind: HistoryKind, request: HistoryRequest
    ) -> None:
        try:
            if kind is HistoryKind.ORDERS:
                orders = self._activity.order_history(request)
                view: HistoryView[object] = history_view_for(
                    orders, build_order_history_row
                )
            else:
                trades = self._activity.trade_history(request)
                view = history_view_for(trades, build_trade_history_row)
            self._read.emit((action_id, kind, view, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._read.emit((action_id, kind, None, str(exc)))

    def _on_read(self, payload: tuple) -> None:
        action_id, kind, view, error = payload
        reads = self._reads[kind]
        if not reads.is_current_pending(action_id, kind.value):
            reads.log_stale_callback("_on_read", action_id, kind.value)
            return
        if view is None:
            reads.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning(
                "Account tabs could not read the %s history: %s", kind.value, error
            )
            self._display.show_history_error(
                kind, f"Could not read the {kind.value} history: {error}"
            )
            return
        reads.finish_action(action_id, ActionOutcome.SUCCEEDED)
        logger.debug(
            "Account tabs read %s page %d of %d (%s)",
            kind.value,
            view.page + 1,
            view.page_count,
            self._requests[kind].symbol or "every active pair",
        )
        self._display.show_history(kind, view)
