"""`FakeTradingSession` — `ITradingSession`'s verified fake.

In-memory, deterministic, no Qt and no network. A test says what the session
looks like, what `ensure_ready()` / `emergency_stop()` answer — or which of them
raises — then reads back how many times each was asked.

@par Why the snapshot is stored rather than derived
The real service reads three fields out of a lock-guarded service in one
critical section. The fake has no lock and needs none — but it must not let a
test mutate a snapshot it already handed out, which is the bug a mutable
stand-in invites. `TradingSessionSnapshot` is frozen, so `answer_with()`
replaces the whole value instead of editing fields.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistration,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionReadyResult,
)

#: What a fresh fake reports: session closed, nothing sent, nothing open. The same
#: state a real `TradingSessionState` starts in — a deliberate action opens it
#: every session (`EPIC-021G`, `EPIC-034C`), so a fake that started open
#: would let a test pass against a state the app never boots into.
_FRESH = TradingSessionSnapshot(
    enabled=False, orders_sent_this_session=0, known_open_symbols=()
)


def _stopped(detail: str) -> EmergencyStopStepResult:
    return EmergencyStopStepResult(succeeded=True, detail=detail)


class FakeTradingSession(ITradingSession):
    """The session state a test says the app is in."""

    def __init__(self, snapshot: TradingSessionSnapshot = _FRESH) -> None:
        self._snapshot = snapshot
        self._ready_result: SessionReadyResult | None = None
        self._stop_result: EmergencyStopResult | None = None
        self._ready_error: Exception | None = None
        self._stop_error: Exception | None = None
        #: How many times each call was made. Named separately because a
        #: screen calling `snapshot()` per repaint is a defect a test should
        #: be able to see, and it looks nothing like calling `ensure_ready()` twice.
        self.snapshot_reads = 0
        self.ready_requests = 0
        self.emergency_stops = 0
        #: `EPIC-025` PR 2.1f — the lease, kept the way the real state keeps
        #: it: **one symbol per owner**, so claiming a second releases the
        #: first. A fake that allowed one owner two symbols would let a
        #: consumer's test pass against a state the real session cannot be in,
        #: which is the `BUG-026`/`BUG-027` failure the contract suite exists
        #: to stop.
        #:
        #: `lease_holder()` is on the port since `EPIC-034H`: the Bots screen
        #: shows before the click who holds a symbol, and the contract suite
        #: proves it. (An earlier reader was deleted when nothing used it; a
        #: helper a fake adds beyond its port is what `BUG-120` was.)
        self._symbol_by_owner: dict[str, str] = {}
        #: `EPIC-029` ADR D6 — the budgets registered this session, by owner.
        #: Cleared on Emergency Stop, as the real state clears
        #: its books.
        self.budgets: dict[str, OwnerBudgetRegistration] = {}
        self._registration_answer: OwnerBudgetRegistrationResult | None = None

    def answer_with(self, snapshot: TradingSessionSnapshot) -> None:
        """Sets what the next `snapshot()` reports."""
        self._snapshot = snapshot

    def set_enabled(self, *, enabled: bool) -> None:
        """The common case spelled out, so a test does not rebuild the whole
        frozen snapshot to flip one flag."""
        self._snapshot = TradingSessionSnapshot(
            enabled=enabled,
            orders_sent_this_session=self._snapshot.orders_sent_this_session,
            known_open_symbols=self._snapshot.known_open_symbols,
        )

    def ready_answers(self, result: SessionReadyResult) -> None:
        self._ready_result = result

    def emergency_stop_answers(self, result: EmergencyStopResult) -> None:
        self._stop_result = result

    def register_owner_budget_answers(
        self, result: OwnerBudgetRegistrationResult
    ) -> None:
        """Sets what a registration made while trading is on answers; a
        refusal registers nothing."""
        self._registration_answer = result

    def ready_raises(self, error: Exception) -> None:
        """Makes the next `ensure_ready()` raise instead of answering.

        A refusal is a *result* (`SessionReadyResult.block_reason`), never an
        exception — but the two network round trips behind it can still fail,
        and a caller that lets that reach the UI thread as an uncaught
        exception is a defect. Both Presenters carry a test for exactly that,
        and this is how they produce it without substituting the port
        (HLD §10.3 rule 4).
        """
        self._ready_error = error

    def emergency_stop_raises(self, error: Exception) -> None:
        """The same, for `emergency_stop()` — where it matters more: the button
        must report a failure, and must never leave the screen believing
        trading is still on."""
        self._stop_error = error

    def snapshot(self) -> TradingSessionSnapshot:
        self.snapshot_reads += 1
        return self._snapshot

    def ensure_ready(self) -> SessionReadyResult:
        self.ready_requests += 1
        if self._ready_error is not None:
            raise self._ready_error
        if self._ready_result is None:
            # The default is a *successful* open, and it also updates the
            # snapshot: a fake whose `ensure_ready()` left `snapshot().enabled`
            # False would let a caller's "did it open?" assertion pass for
            # the wrong reason.
            self.set_enabled(enabled=True)
            return SessionReadyResult(
                ready=True,
                block_reason=None,
                reconciled_positions=(),
                reconciled_open_orders=(),
            )
        if self._ready_result.ready:
            self.set_enabled(enabled=True)
        return self._ready_result

    def register_owner_budget(
        self, registration: OwnerBudgetRegistration
    ) -> OwnerBudgetRegistrationResult:
        if not self._snapshot.enabled:
            return OwnerBudgetRegistrationResult(OwnerBudgetRefusal.TRADING_SWITCH_OFF)
        answer = self._registration_answer or OwnerBudgetRegistrationResult(
            None, EMPTY_INVENTORY
        )
        if answer.registered:
            self.budgets[registration.owner_id] = registration
        return answer

    def clear_owner_budget(self, owner_id: str) -> None:
        self.budgets.pop(owner_id, None)

    def claim_symbol(self, symbol: str, owner_id: str) -> bool:
        holder = next(
            (owner for owner, held in self._symbol_by_owner.items() if held == symbol),
            None,
        )
        if holder is not None and holder != owner_id:
            return False
        self._symbol_by_owner[owner_id] = symbol
        return True

    def lease_holder(self, symbol: str) -> str | None:
        return next(
            (owner for owner, held in self._symbol_by_owner.items() if held == symbol),
            None,
        )

    def release_symbol(self, symbol: str, owner_id: str) -> None:
        if self._symbol_by_owner.get(owner_id) == symbol:
            del self._symbol_by_owner[owner_id]

    def emergency_stop(self) -> EmergencyStopResult:
        self.emergency_stops += 1
        if self._stop_error is not None:
            # Raised *before* the state changes: a stop that failed on the
            # network did not disable anything, and a fake that turned trading
            # off anyway would let a caller's "did it recover?" assertion pass
            # for the wrong reason.
            raise self._stop_error
        self.set_enabled(enabled=False)
        self.budgets.clear()
        if self._stop_result is None:
            return EmergencyStopResult(
                trading_disabled=_stopped("disabled"),
                orders_cancelled=_stopped("no open orders"),
                positions_closed=_stopped("no open positions"),
                final_state_confirmed=True,
            )
        return self._stop_result
