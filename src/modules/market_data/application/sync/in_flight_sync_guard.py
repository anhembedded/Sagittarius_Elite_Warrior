from __future__ import annotations

import threading


class InFlightSyncGuard:
    """
    @brief Thread-safe registry of `(symbol, interval)` pairs currently mid-sync.

    @details `BOT-121`: `SyncMarketDataCommandHandler` is the single choke point every
    sync dispatch passes through — Backtest's `DataSyncCoordinator`, Data Management's
    `SyncCoordinator.run_single_sync()`, and `BulkSyncMarketDataCommandHandler` (which
    itself just dispatches one `SyncMarketDataCommand` per target) all end up calling
    `execute()` on it. Reserving a `(symbol, interval)` key there, and only there, means
    no caller can fetch the same pair from the exchange twice concurrently, regardless of
    which screen (or how many) asked for it.

    Deliberately not `ExclusiveAction` (`sagittarius_engine`, `BOT-069`): that primitive
    holds exactly one slot per instance — every key sharing an instance excludes every
    other key. Bulk sync intentionally runs distinct `(symbol, interval)` targets
    concurrently on a thread pool; wrapping that in an `ExclusiveAction` would serialize
    it down to one target at a time. This class excludes only identical keys from each
    other — different keys never block one another.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_flight: set[tuple[str, str]] = set()

    def try_acquire(self, symbol: str, interval: str) -> bool:
        """
        @brief Reserves `(symbol, interval)` if nothing else currently holds it.
        @returns True if reserved — caller now owns it and must eventually call
        `release()` (normally in a `finally`). False if already held elsewhere.
        """
        key = (symbol, interval)
        with self._lock:
            if key in self._in_flight:
                return False
            self._in_flight.add(key)
            return True

    def release(self, symbol: str, interval: str) -> None:
        """@brief Releases `(symbol, interval)` if held — a no-op otherwise."""
        with self._lock:
            self._in_flight.discard((symbol, interval))
