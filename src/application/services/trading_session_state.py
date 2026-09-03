"""`EPIC-021G` — the in-memory record of "is live trading on right now, and
what does this app currently believe about the account".

@details Deliberately **not** persisted, and deliberately **not** read
from `ConfigKeys.TRADING_ENABLED`'s saved value on boot — `EPIC-021G` §2.3
point 2 requires the user to turn trading on explicitly every session,
the one place in this app that intentionally does not follow `EPIC-010`'s
normal "remember what the user last set" convention. A fresh
`TradingSessionState` is always `enabled=False`; only `EnableTradingCommand`
(after it re-reconciles against the exchange) may flip it on.

`known_open_symbols` starts as whatever `EnableTradingCommand`'s
reconciliation found, and grows conservatively afterward:
`record_order_sent()` marks a symbol as "assume open" the moment an order
for it is sent, before this app has any confirmation it filled — safer to
over-block a second order on the same symbol than to under-block one,
pending `EPIC-021H`'s User Data Stream becoming the real source of truth
for whether it actually did.

`BUG-088` — every mutation goes through `self._lock`: `record_order_sent()`
(the `ExecuteOrderCommand` pool worker), `reconcile_position()` (the
websocket thread `FuturesUserDataStream` runs on), and `enable()`/
`disable()` (the `EnableTradingCommand`/`DisableTradingCommand`/
`EmergencyStopCommand` pool workers) are reachable from three genuinely
different threads in production, not merely hypothetically — without the
lock, two of them landing between the same two Python bytecodes can corrupt
`known_open_symbols`/`_last_order_time_by_symbol`.

The lock alone does not stop `EnableTradingCommand`'s two network round-trips
from *finishing after* a concurrent Emergency Stop's `disable()` and
blindly turning trading back on — reconciliation succeeding doesn't mean
nothing else happened while it ran. `enable()`'s `expected_generation`
closes that: a caller reads `self.generation` before starting its own
network calls, then only applies if nothing else mutated state meanwhile.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta


class TradingSessionState:
    """Plain mutable service, one instance per app process (a DI
    singleton) — deliberately not a frozen value object, since its whole
    job is to be mutated in place as orders go out."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.enabled = False
        self.orders_sent_this_session = 0
        self.known_open_symbols: set[str] = set()
        self._last_order_time_by_symbol: dict[str, datetime] = {}
        #: Bumped by every state-changing call. See `enable()`'s own
        #: docstring for what this guards against.
        self._generation = 0

    @property
    def generation(self) -> int:
        return self._generation

    def enable(
        self, open_symbols: set[str], *, expected_generation: int | None = None
    ) -> bool:
        """@brief Turns trading on for this session, seeded with
        `open_symbols` from a just-completed reconciliation.

        @details `expected_generation`, when given, makes this a
        conditional apply: only takes effect if `self.generation` still
        equals it, i.e. nothing else (a concurrent `disable()`, another
        `enable()`, an order, a reconciliation) mutated this state since
        the caller read it — the caller is expected to have read
        `self.generation` *before* doing whatever network round-trips led
        up to this call. Returns whether it actually applied; a caller
        that gets `False` back was superseded and must not proceed as if
        it had enabled trading (`BUG-088` — this is what stops
        `EnableTradingCommand` from re-enabling trading right after an
        Emergency Stop that ran while it was still reconciling).
        """
        with self._lock:
            if (
                expected_generation is not None
                and expected_generation != self._generation
            ):
                return False
            self.enabled = True
            self.known_open_symbols = set(open_symbols)
            self._generation += 1
            return True

    def disable(self) -> None:
        with self._lock:
            self.enabled = False
            self._generation += 1

    def open_position_count(self, symbol: str) -> int:
        """@brief One-way mode (assumed throughout this epic) means a
        symbol is either flat (0) or has exactly one open position (1) —
        never a real count, but shaped as one so `TradingLimitContext`
        stays generalizable if that assumption ever needs to loosen."""
        with self._lock:
            return 1 if symbol in self.known_open_symbols else 0

    def time_since_last_order(self, symbol: str, now: datetime) -> timedelta | None:
        with self._lock:
            last = self._last_order_time_by_symbol.get(symbol)
            return None if last is None else now - last

    def record_order_sent(self, symbol: str, when: datetime) -> None:
        with self._lock:
            self.orders_sent_this_session += 1
            self._last_order_time_by_symbol[symbol] = when
            self.known_open_symbols.add(symbol)
            self._generation += 1

    def reconcile_position(self, symbol: str, *, has_position: bool) -> bool:
        """@brief Corrects `known_open_symbols` for `symbol` to match
        `has_position` (what the exchange just reported).
        @return Whether this app's prior belief disagreed — the caller
        (`position_state_reconciler.py`) logs on `True`, kept out of this
        method so the lock's critical section stays a pure state update."""
        with self._lock:
            was_known_open = symbol in self.known_open_symbols
            if has_position:
                self.known_open_symbols.add(symbol)
            else:
                self.known_open_symbols.discard(symbol)
            self._generation += 1
            return was_known_open != has_position
