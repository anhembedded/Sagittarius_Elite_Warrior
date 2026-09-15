"""Port: *is live trading on, and turn it on or off* (HLD §3.4).

**Why this port exists, and the part that is not about imports.** Three
Presenters and the Settings screen read `TradingSessionState` **directly** —
a mutable, lock-guarded application service, reached from the UI thread while
the websocket thread mutates it (`BUG-088` is why it has a lock at all). The
boundary allowlist counted that as five entries; the real cost is that a
screen could read `known_open_symbols` while
`FuturesUserDataStream.reconcile_position()` was rewriting it.

`snapshot()` answers with a frozen value instead. Measured, those four files
read exactly three facts off the state — `enabled`,
`orders_sent_this_session`, `known_open_symbols` — so those three are what
`TradingSessionSnapshot` carries and nothing else (HLD §2.4).

@par No symbol lease yet, and that is deliberate
HLD §3.4's worked example gives this port `claim_symbol(symbol, owner_id)` /
`release_symbol(...)` — an **exclusive lease that refuses**, so a manual order
cannot be placed on a symbol a strategy is armed on. It is not here, for the
reason `architecture-rule.md` §7.2.1 gives: the lease's first consumer is
`strategy`, which claims on arm and releases on disarm, and `strategy` is
Phase 2. A lease published now would be an exclusive-locking mechanism on
shared mutable state with **no caller** — new behaviour on the riskiest state
in the app, which ADR D12 keeps out of a port pull request. Phase 2 adds it
under the existing lock, with claim-then-execute as one critical section,
which is the design HLD §3.4 already argues.

The same shape as `IMarketStream`'s missing `StreamHandle` (PR 1.1b) and for
the same reason: the seam is cut when the second consumer arrives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingResult,
)


@dataclass(frozen=True, slots=True)
class TradingSessionSnapshot:
    """What this app believes about the live trading session, right now.

    A **snapshot**, and the name is the promise: reading it twice may give
    two different answers, and neither is stale in the sense of being wrong —
    the session genuinely changes underneath (`domain-truth-rule.md`'s
    immutable-snapshot rule). What it will never do is change while a caller
    is halfway through reading it.
    """

    #: Whether live submission is currently allowed. Never persisted across
    #: runs: `EPIC-021G` requires the user to turn trading on explicitly every
    #: session, the one place this app deliberately does not remember the last
    #: value the user set.
    enabled: bool
    #: Orders sent since this process started — the counter the session's
    #: `max_orders_per_session` limit is checked against.
    orders_sent_this_session: int
    #: Symbols this app assumes hold an open position. Conservative by design:
    #: a symbol is added the moment an order for it is *sent*, before any fill
    #: confirmation, because over-blocking a second order is safer than
    #: under-blocking one.
    known_open_symbols: tuple[str, ...]


class ITradingSession(ABC):
    """Read the live trading session, and turn it on or off."""

    @abstractmethod
    def snapshot(self) -> TradingSessionSnapshot:
        """The session's three facts, frozen. Cheap — no network, no lock held
        after it returns."""

    @abstractmethod
    def enable(self) -> EnableTradingResult:
        """Reconcile against the exchange and, if that succeeds, allow live
        submission.

        Two network round trips, then a generation check: reconciliation
        succeeding does not mean nothing else happened while it ran, so a
        concurrent Emergency Stop wins and this answers `enabled=False` with a
        named `block_reason` rather than blindly turning trading back on.
        """

    @abstractmethod
    def disable(self) -> None:
        """Stop allowing live submission. Returns nothing because it cannot
        refuse — it always succeeds, which is why there is no
        `DisableTradingResult`."""

    @abstractmethod
    def emergency_stop(self) -> EmergencyStopResult:
        """Disable, cancel every open order, close every position, then read
        the account back to confirm.

        Each of the three steps answers separately
        (`EmergencyStopStepResult`) because a partial stop is a real outcome
        the user must see: "orders cancelled, positions still open" is
        different from "nothing happened", and both are different from
        `final_state_confirmed`.
        """
