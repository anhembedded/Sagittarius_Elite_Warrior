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

@par The symbol lease, since PR 2.1f — and where the refusal actually lives
`claim_symbol(symbol, owner_id)` / `release_symbol(...)`: `strategy` claims on
arm and releases on disarm, and the order path refuses an order on a symbol
somebody else has claimed. It waited for Phase 2 because its first consumer is
`strategy` (`architecture-rule.md` §7.2.1 — cut the seam at the consumer, not
ahead of it), and PR 2.1f is where that consumer arrived.

**What it changes is which layer enforces a rule, not the rule.** The refusal
already existed: `DashboardPresenter._run_manual_order()` read
`IArmedStrategy.armed()` and hard-blocked a manual Long/Short on the armed
symbol, per the user's decision of 2026-09-09 (`PRO-003` §4.1.2). A **UI class
enforcing a trading safety rule** is backwards — `architecture-rule.md` §3 — and
bypassable by any order path that is not that one form. Measured before moving
it: three callers reach `IOrderSubmission.submit()`, and only one of them had
the check. So it moves into `ExecuteOrderCommandHandler`, where every caller
inherits it, as a fourth `ExecuteOrderSafetyGate`.

`claim_symbol` returns a `bool` rather than nothing, and that is the honest
shape even though it cannot fail today: with one armed strategy there is never
a second owner. Two strategies on two symbols is ADR §7 item 15's seam, and
when it arrives the refusal is already expressible.

The lease is **in-process**, like everything else on `TradingSessionState`. A
second process is not protected by it and does not need to be: `enabled` is
never persisted (`EPIC-021G` §2.3), so a fresh `trade-once --live` is already
refused by `TRADING_SWITCH_OFF` before any lease is consulted — checked, not
assumed, because the reverse would have been a real hole.
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
    def claim_symbol(self, symbol: str, owner_id: str) -> bool:
        """Declare that `owner_id` is managing `symbol`, so the order path
        refuses anyone else's order on it.

        @return `False` when a different owner already holds it; nothing is
        changed in that case.
        @details One symbol per owner: claiming a second **replaces** the
        first, because re-arming a strategy onto another symbol must not leave
        the old one claimed by nobody. Re-claiming what you hold succeeds.
        """

    @abstractmethod
    def release_symbol(self, symbol: str, owner_id: str) -> None:
        """Give up `owner_id`'s claim on `symbol`.

        @details A no-op when this owner does not hold it. It can never
        release another owner's lease — that is the half that matters, since
        the point of the lease is that a manual order path cannot clear the
        strategy's claim to let itself through.
        """

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
