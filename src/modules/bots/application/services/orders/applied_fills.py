"""`EPIC-035P` — which fills this run has already counted.

The user-data stream may deliver one `executionReport` twice (a reconnect, a
redelivery), and the reconciler may apply from history a fill the stream then
delivers after all. The exchange's trade id says which fill a report is, so a
fill is the pair (client order id, trade id): one the run has seen is counted
once, whichever of the two sources reports it again.

A fill with no trade id (a venue that reports none) is never known: nothing is
guessed from its quantity. Only the worker touches it, it lives for one run (a
restart reads what the exchange holds, `GridReconciler`), and it keeps the most
recent `limit` fills, which is far more than a ladder produces between two
reconciles: a duplicate arrives within seconds of the original.
"""

from __future__ import annotations

from collections import OrderedDict

#: How many fills the run remembers.
DEFAULT_REMEMBERED_FILLS = 4096


class AppliedFills:
    """The (order, trade) pairs the run has counted, bounded."""

    def __init__(self, limit: int = DEFAULT_REMEMBERED_FILLS) -> None:
        self._limit = limit
        self._seen: OrderedDict[tuple[str, int], None] = OrderedDict()

    def knows(self, client_order_id: str, trade_id: int | None) -> bool:
        """Whether this fill was already counted."""
        return trade_id is not None and (client_order_id, trade_id) in self._seen

    def record(self, client_order_id: str, trade_id: int | None) -> None:
        """Count this fill as seen from now on (`None`: nothing to remember)."""
        if trade_id is None:
            return
        key = (client_order_id, trade_id)
        self._seen[key] = None
        self._seen.move_to_end(key)
        while len(self._seen) > self._limit:
            self._seen.popitem(last=False)
