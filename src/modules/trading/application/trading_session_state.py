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

`EPIC-024B` — `live_submission_guard()` is a **second**, separate lock.
`PRO-003` §8.2 asked directly: with a second real caller of
`ExecuteOrderCommand` now possible (a human clicking Long/Short on the
manual trading form, alongside the strategy's own tick), can two concurrent
dispatches both read `orders_sent_this_session` before either one's order
actually lands and its increment applies — letting both through when only
one slot was free? Reading `ExecuteOrderCommandHandler.execute()` before
this epic confirmed yes: evaluate-then-submit-then-record spanned a real
network call with no lock held across it at all. `self._lock` above cannot
be reused to fix this — every accessor here takes and releases it almost
immediately by design (`open_position_count()`, `time_since_last_order()`),
and holding it across a network call would block those for unrelated
readers (UI polling) for the duration of an order. `live_submission_guard()`
exists for callers that specifically need the opposite: the whole
evaluate→submit→record sequence serialized against every other live
dispatch, network call included. Order submission is inherently rare
(bounded by `TradingLimits.min_order_interval` already) and the realistic
contention here is at most two callers, so serializing them is the correct
trade-off, not a bottleneck.
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
        #: `EPIC-024B` — see this class's own docstring for why this is a
        #: second, distinct lock from `self._lock` above. `RLock`, not
        #: `Lock`: nothing today calls back into `ExecuteOrderCommandHandler.
        #: execute()` while already holding this (re-checked when it was
        #: added), but a plain `Lock` would deadlock outright if that ever
        #: changed, instead of failing a test loudly — `RLock` costs nothing
        #: here (this is not a hot path) and removes that failure mode.
        self._live_submission_lock = threading.RLock()
        self.enabled = False
        self.orders_sent_this_session = 0
        self.known_open_symbols: set[str] = set()
        self._last_order_time_by_symbol: dict[str, datetime] = {}
        #: `EPIC-025` PR 2.1f — the symbol lease: who, if anyone, has declared
        #: that they are managing a symbol. **One entry per owner, not per
        #: symbol**, and that is the invariant: an owner claiming a second
        #: symbol releases its first, so re-arming a strategy onto a different
        #: symbol cannot leave the old one leased by a strategy nobody is
        #: running. Keyed by owner for exactly that reason; the order path asks
        #: the reverse question (`lease_holder(symbol)`) and pays a scan of a
        #: dict that holds at most one entry today.
        self._symbol_by_owner: dict[str, str] = {}
        #: Bumped by every state-changing call. See `enable()`'s own
        #: docstring for what this guards against.
        self._generation = 0

    @property
    def generation(self) -> int:
        return self._generation

    def live_submission_guard(self) -> threading.RLock:
        """@brief The lock `ExecuteOrderCommandHandler` holds across its
        entire evaluate-limits→submit→record sequence for a live order —
        see this class's own docstring (`EPIC-024B`) for why. A `threading.
        RLock` is already a context manager
        (`with state.live_submission_guard():`); returned rather than
        wrapped so callers get the standard `with`/`acquire`/`release`
        surface without this class inventing its own.
        """
        return self._live_submission_lock

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

    def read_all(self) -> tuple[bool, int, tuple[str, ...]]:
        """@brief The three facts a reader outside this module needs, read as
        **one** critical section.

        @details `EPIC-025` PR 1.3b. `enabled`, `orders_sent_this_session` and
        `known_open_symbols` are plain attributes, so three separate reads can
        interleave with `record_order_sent()` on the order thread or
        `reconcile_position()` on the websocket thread and return a
        combination that never existed — enabled from before a disable, with a
        symbol set from after it. Taking `self._lock` once is what makes
        `ITradingSession.snapshot()` able to promise a coherent answer.

        Returns a tuple rather than the published `TradingSessionSnapshot`
        because this class is `application/` and the DTO is `contracts/`:
        mapping the tuple is `TradingSessionService`'s one line, and it keeps
        this file free of the published vocabulary.

        `known_open_symbols` is copied into a tuple **inside** the lock. The
        set itself is mutable and shared; handing a reader the live object
        would be handing them a race dressed as a value.
        """
        with self._lock:
            return (
                self.enabled,
                self.orders_sent_this_session,
                tuple(sorted(self.known_open_symbols)),
            )

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

    def claim_symbol(self, symbol: str, owner_id: str) -> bool:
        """@brief Declares that `owner_id` is managing `symbol`.
        @return `False` when a **different** owner already holds it, and
        nothing is changed; `True` when the lease is now this owner's.
        @details Re-claiming what you already hold succeeds. Claiming a second
        symbol **replaces** your first — see `_symbol_by_owner`'s note for why
        that is the invariant rather than an accident: `LiveStrategySession.
        arm()` re-arms without disarming first, so a per-symbol lease would
        strand the previous symbol.
        """
        with self._lock:
            holder = next(
                (
                    owner
                    for owner, held in self._symbol_by_owner.items()
                    if held == symbol
                ),
                None,
            )
            if holder is not None and holder != owner_id:
                return False
            self._symbol_by_owner[owner_id] = symbol
            self._generation += 1
            return True

    def release_symbol(self, symbol: str, owner_id: str) -> None:
        """@brief Gives up `owner_id`'s claim on `symbol`.
        @details A no-op when this owner does not hold that symbol — releasing
        something you never claimed is not an error, and refusing it would make
        every caller check first. It cannot release *another* owner's lease,
        which is the half that matters: the whole point is that a manual order
        path cannot clear the strategy's claim to get itself through.
        """
        with self._lock:
            if self._symbol_by_owner.get(owner_id) == symbol:
                del self._symbol_by_owner[owner_id]
                self._generation += 1

    def lease_holder(self, symbol: str) -> str | None:
        """@brief Who has declared they are managing `symbol`, if anyone.

        @details Read by `ExecuteOrderCommandHandler` **inside**
        `live_submission_guard()`, so the check and the submission it gates are
        one critical section (`Docs/SDD/05` §3's claim-then-execute). Reading it
        before that lock would let a strategy arm in the gap between the check
        and the order.
        """
        with self._lock:
            for owner, held in self._symbol_by_owner.items():
                if held == symbol:
                    return owner
            return None

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
