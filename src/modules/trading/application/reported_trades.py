"""`BOT-173` — which trades the venue's fills have already been counted for.

A fill reaches the app in more than one record (the placement response, the
user-data stream, a history re-read), and the exchange's trade id says which
trade a record is: one reported once is not counted again, whichever record
comes second. The key is (symbol, trade id), since a Spot trade id is unique
per symbol. A fill with no trade id cannot be recognised and is never
"reported"; nothing is guessed from its quantity.

The shape is the bots' `AppliedFills` (`EPIC-035P`) on trading's side of the
boundary: a bounded, most-recent-first memory, far more than the fills between
two records of one trade, which arrive within seconds of each other. Not
thread-safe by itself: the order pool and the websocket both report, so a lock
guards it.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

#: How many trades a venue remembers.
DEFAULT_REMEMBERED_TRADES = 8192


class ReportedTrades:
    """The (symbol, trade id) pairs already reported, bounded."""

    def __init__(self, limit: int = DEFAULT_REMEMBERED_TRADES) -> None:
        self._limit = limit
        self._lock = threading.Lock()
        self._seen: OrderedDict[tuple[str, int], None] = OrderedDict()

    def claim(self, symbol: str, trade_id: int | None) -> bool:
        """@brief Whether this is the first record of the trade (it is then claimed:
        later records of it answer False). A fill with no trade id is always treated as a first
        report: it cannot be told from another."""
        if trade_id is None:
            return True
        key = (symbol, trade_id)
        with self._lock:
            if key in self._seen:
                return False
            self._seen[key] = None
            while len(self._seen) > self._limit:
                self._seen.popitem(last=False)
        return True
