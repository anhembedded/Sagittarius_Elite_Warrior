"""`EPIC-047H` — `IMarkBoard` in memory: one slot per venue and symbol, under a lock."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_board import (
    IMarkBoard,
    RecordedMark,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class MemoryMarkBoard(IMarkBoard):
    """Called from every thread that reads a mark (each bot's worker) and from the recorder's worker,
    so every access takes the lock; the slots are as many as there are symbols watched."""

    def __init__(self, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._now = now
        self._lock = threading.Lock()
        self._latest: dict[tuple[str, str], RecordedMark] = {}

    def record(
        self, venue: TradingVenue, symbol: str, mark_price: Decimal, as_of: datetime
    ) -> None:
        mark = RecordedMark(venue, symbol, mark_price, as_of, self._now())
        with self._lock:
            self._latest[(venue.value, symbol)] = mark

    def latest(self) -> tuple[RecordedMark, ...]:
        with self._lock:
            held = dict(self._latest)
        return tuple(held[key] for key in sorted(held))
