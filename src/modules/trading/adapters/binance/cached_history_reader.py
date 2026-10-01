"""`EPIC-028Q` — `IAccountHistoryReader` that reads a span from the exchange
at most once per `ttl`.

@details Every page of a history query re-runs the whole query: the handler
reads each symbol's span, merges, sorts and slices one page out of it. On
Spot a seven-day span is eight windows of weight 20, per symbol and per
endpoint, so a few page clicks across five pairs pass Binance's 6 000 weight a
minute (the PR #300 epic review, §3 item 5). This reader answers a repeated
read from the last one: for `ttl` after reading `(symbol, since)` it serves
any `since` at or after the cached one, with the rows from that `since` on. A
read further back, or after `ttl`, goes to the exchange and replaces the
entry. `active_symbols` is served only for the same `since`, because a
different `since` names different pairs. A failed read is never cached.

The cost is freshness: a fill is seen at most `ttl` late. The lookback check
runs on every call, so a cached answer never passes a `since` the exchange
readers would refuse.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_reads import (
    utc_now,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_gaps import (
    HistoryGaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_lookback import (
    require_within_lookback,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

logger = logging.getLogger("App.HistoryCache")

#: Long enough to page through a history, short enough that a fill shows up
#: on the next look.
HISTORY_CACHE_TTL = timedelta(seconds=15)


@dataclass(frozen=True)
class _Entry[T]:
    since: datetime
    read_at: datetime
    value: T


class _SymbolHistoryCache[T]:
    """One history kind's entries, one per symbol: the reuse rule lives
    here once for orders and trades alike."""

    def __init__(
        self,
        kind: str,
        read: Callable[[str, datetime], tuple[T, ...]],
        row_time: Callable[[T], datetime],
    ) -> None:
        self._kind = kind
        self._read = read
        self._row_time = row_time
        self._entries: dict[str, _Entry[tuple[T, ...]]] = {}

    def rows(
        self, symbol: str, since: datetime, freshness: _Freshness
    ) -> tuple[T, ...]:
        with freshness.lock:
            entry = self._entries.get(symbol)
        if entry is not None and entry.since <= since and freshness.fresh(entry):
            logger.debug(
                "[history-cache] %s %s since %s: cached", self._kind, symbol, since
            )
            return tuple(row for row in entry.value if self._row_time(row) >= since)
        logger.debug("[history-cache] %s %s since %s: read", self._kind, symbol, since)
        rows = self._read(symbol, since)
        with freshness.lock:
            self._entries[symbol] = _Entry(since, freshness.now, rows)
        return rows


@dataclass(frozen=True)
class _Freshness:
    """The moment one call started, the TTL it judges entries by, and the
    lock every entry is read and written under."""

    now: datetime
    ttl: timedelta
    lock: threading.Lock

    def fresh[T](self, entry: _Entry[T]) -> bool:
        # A clock stepped back counts as stale, never as fresh forever.
        return timedelta(0) <= self.now - entry.read_at < self.ttl


class CachedAccountHistoryReader(IAccountHistoryReader):
    """Serves repeated history reads from the last exchange read."""

    def __init__(
        self,
        inner: IAccountHistoryReader,
        *,
        ttl: timedelta = HISTORY_CACHE_TTL,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._inner = inner
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._orders = _SymbolHistoryCache[OrderRecord](
            "orders", inner.order_history, lambda row: row.created_at
        )
        self._trades = _SymbolHistoryCache[TradeRecord](
            "trades", inner.trade_history, lambda row: row.time
        )
        self._symbols: _Entry[tuple[str, ...]] | None = None

    @property
    def source(self) -> IAccountHistoryReader:
        """The reader a cache miss goes to."""
        return self._inner

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        return self._orders.rows(symbol, since, self._freshness(since))

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        return self._trades.rows(symbol, since, self._freshness(since))

    def active_symbols(self, since: datetime) -> tuple[str, ...]:
        freshness = self._freshness(since)
        with self._lock:
            entry = self._symbols
        if entry is not None and entry.since == since and freshness.fresh(entry):
            logger.debug("[history-cache] active symbols since %s: cached", since)
            return entry.value
        logger.debug("[history-cache] active symbols since %s: read", since)
        symbols = self._inner.active_symbols(since)
        with self._lock:
            self._symbols = _Entry(since, freshness.now, symbols)
        return symbols

    def known_gaps(self) -> HistoryGaps:
        return self._inner.known_gaps()

    def _freshness(self, since: datetime) -> _Freshness:
        now = self._clock()
        require_within_lookback(since, now)
        return _Freshness(now, self._ttl, self._lock)
