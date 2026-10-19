"""`EPIC-039C` — the faults only a matching engine can have: late, duplicated, rejected.

@details Off by default, so a test that never touches them sees the fake it always saw.
HTTP-level faults (a 429, a dropped connection, a wrong body) stay with `FaultPlan` in
`server.py`; these live inside the book, where `OrderBookState.place` and `move_price`
consult them, so they work in a unit test with no server and through HTTP alike.
"""

from __future__ import annotations

from collections import deque


class MatchFaults:
    """Switches a test sets, in the spirit of `EPIC-037E`."""

    def __init__(self) -> None:
        #: While set, a price move fills nothing; `OrderBookState.release_fills()`
        #: fills what the latest price crosses (a fill that arrives late).
        self.hold_fills = False
        #: While set, every fill's `ORDER_TRADE_UPDATE` is queued twice (a duplicated
        #: report); the position, the wallet and the trade list are unaffected.
        self.duplicate_reports = False
        #: While set, the open-orders list lags the exchange: an order cancelled meanwhile
        #: still shows in it (a cancel the list has not caught up with), though a second
        #: cancel of it answers `-2011` as for any unknown order. Unset, the list is true.
        self.stale_open_orders = False
        self._cancelled: dict[str, dict[str, object]] = {}
        self._rejections: deque[tuple[int, str]] = deque()

    def reject_next_order(self, code: int, message: str) -> None:
        """The next order is refused with Binance's error shape `{code, msg}` and
        remembered nowhere."""
        self._rejections.append((code, message))

    def take_rejection(self) -> tuple[int, dict[str, object]] | None:
        if not self._rejections:
            return None
        code, message = self._rejections.popleft()
        return 400, {"code": code, "msg": message}

    def note_cancelled(self, client_order_id: str, order: dict[str, object]) -> None:
        self._cancelled[client_order_id] = order

    def lagging_orders(self) -> list[dict[str, object]]:
        """The cancelled orders the open-orders list still shows, while it lags."""
        return list(self._cancelled.values()) if self.stale_open_orders else []
