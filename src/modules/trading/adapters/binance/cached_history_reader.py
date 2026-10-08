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

**A read already in flight is joined, not repeated** (`BUG-145`): a desk reads
its histories when it opens and again when trading is turned on, and the
second every-pair read used to miss the cache for every pair the first was
still reading, spending Binance's weight twice. A read of a key that is being
read waits for that read and is then judged against the entry it stored; if
that read failed, or its entry does not serve the waiting `since`, the waiting
read goes to the exchange itself.

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveSymbol,
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


class _ReadsInFlight[K]:
    """The reads of one kind now going to the exchange, by key, so a second
    read of a key waits for the first instead of repeating it (`BUG-145`)."""

    def __init__(self, kind: str, lock: threading.Lock) -> None:
        self._kind = kind
        self._lock = lock
        self._running: dict[K, threading.Event] = {}

    def read_once[V](
        self, key: K, cached: Callable[[], V | None], read: Callable[[], V]
    ) -> V:
        """@param cached Answers from the cache or `None`; called under the
        lock, so it must not take it.
        @param read Reads the exchange and stores the entry; called with the
        lock released, by at most one caller per key at a time."""
        while True:
            with self._lock:
                hit = cached()
                if hit is not None:
                    return hit
                running = self._running.get(key)
                if running is None:
                    done = threading.Event()
                    self._running[key] = done
                    break
            logger.debug(
                "[history-cache] %s %s: joins the read in flight", self._kind, key
            )
            running.wait()
        try:
            return read()
        finally:
            with self._lock:
                del self._running[key]
            done.set()


class _SymbolHistoryCache[T]:
    """One history kind's entries, one per symbol: the reuse rule lives
    here once for orders and trades alike."""

    def __init__(
        self,
        kind: str,
        read: Callable[[str, datetime], tuple[T, ...]],
        row_time: Callable[[T], datetime],
        lock: threading.Lock,
    ) -> None:
        self._kind = kind
        self._read = read
        self._row_time = row_time
        self._lock = lock
        self._entries: dict[str, _Entry[tuple[T, ...]]] = {}
        self._in_flight = _ReadsInFlight[str](kind, lock)

    def rows(
        self, symbol: str, since: datetime, freshness: _Freshness
    ) -> tuple[T, ...]:
        def cached() -> tuple[T, ...] | None:
            entry = self._entries.get(symbol)
            if entry is None or entry.since > since or not freshness.fresh(entry):
                return None
            logger.debug(
                "[history-cache] %s %s since %s: cached", self._kind, symbol, since
            )
            return tuple(row for row in entry.value if self._row_time(row) >= since)

        def read() -> tuple[T, ...]:
            logger.debug(
                "[history-cache] %s %s since %s: read", self._kind, symbol, since
            )
            rows = self._read(symbol, since)
            with freshness.lock:
                self._entries[symbol] = _Entry(since, freshness.now, rows)
            return rows

        return self._in_flight.read_once(symbol, cached, read)

    def forget(self, symbol: str) -> None:
        with self._lock:
            self._entries.pop(symbol, None)


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
            "orders", inner.order_history, lambda row: row.created_at, self._lock
        )
        self._trades = _SymbolHistoryCache[TradeRecord](
            "trades", inner.trade_history, lambda row: row.time, self._lock
        )
        self._symbols: _Entry[tuple[ActiveSymbol, ...]] | None = None
        self._symbols_in_flight = _ReadsInFlight[datetime]("active symbols", self._lock)

    @property
    def source(self) -> IAccountHistoryReader:
        """The reader a cache miss goes to."""
        return self._inner

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        return self._orders.rows(symbol, since, self._freshness(since))

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        return self._trades.rows(symbol, since, self._freshness(since))

    def discard_remembered(self, symbol: str) -> None:
        """`EPIC-035B` — the next read of `symbol` goes to the exchange. A read
        already in flight still stores its entry when it ends."""
        self._orders.forget(symbol)
        self._trades.forget(symbol)

    def active_symbols(self, since: datetime) -> tuple[ActiveSymbol, ...]:
        freshness = self._freshness(since)

        def cached() -> tuple[ActiveSymbol, ...] | None:
            entry = self._symbols
            if entry is None or entry.since != since or not freshness.fresh(entry):
                return None
            logger.debug("[history-cache] active symbols since %s: cached", since)
            return entry.value

        def read() -> tuple[ActiveSymbol, ...]:
            logger.debug("[history-cache] active symbols since %s: read", since)
            symbols = self._inner.active_symbols(since)
            with self._lock:
                self._symbols = _Entry(since, freshness.now, symbols)
            return symbols

        return self._symbols_in_flight.read_once(since, cached, read)

    def every_symbol_scan_limit(self) -> int | None:
        return self._inner.every_symbol_scan_limit()

    def known_gaps(self) -> HistoryGaps:
        return self._inner.known_gaps()

    def _freshness(self, since: datetime) -> _Freshness:
        now = self._clock()
        require_within_lookback(since, now)
        return _Freshness(now, self._ttl, self._lock)
