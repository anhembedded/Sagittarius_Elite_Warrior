"""`FakeTradingSession` — `ITradingSession`'s verified fake.

In-memory, deterministic, no Qt and no network. A test says what the session
looks like, what `enable()` / `emergency_stop()` answer — or which of them
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
    TradingSessionSnapshot,
)

#: What a fresh fake reports: trading off, nothing sent, nothing open. The same
#: state a real `TradingSessionState` starts in — `EPIC-021G` requires the user
#: to turn trading on explicitly every session, so a fake that started enabled
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
        self._enable_result: EnableTradingResult | None = None
        self._stop_result: EmergencyStopResult | None = None
        self._enable_error: Exception | None = None
        self._stop_error: Exception | None = None
        #: How many times each call was made. Named separately because a
        #: screen calling `snapshot()` per repaint is a defect a test should
        #: be able to see, and it looks nothing like calling `enable()` twice.
        self.snapshot_reads = 0
        self.enables = 0
        self.disables = 0
        self.emergency_stops = 0

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

    def enable_answers(self, result: EnableTradingResult) -> None:
        self._enable_result = result

    def emergency_stop_answers(self, result: EmergencyStopResult) -> None:
        self._stop_result = result

    def enable_raises(self, error: Exception) -> None:
        """Makes the next `enable()` raise instead of answering.

        A refusal is a *result* (`EnableTradingResult.block_reason`), never an
        exception — but the two network round trips behind it can still fail,
        and a caller that lets that reach the UI thread as an uncaught
        exception is a defect. Both Presenters carry a test for exactly that,
        and this is how they produce it without substituting the port
        (HLD §10.3 rule 4).
        """
        self._enable_error = error

    def emergency_stop_raises(self, error: Exception) -> None:
        """The same, for `emergency_stop()` — where it matters more: the button
        must report a failure, and must never leave the screen believing
        trading is still on."""
        self._stop_error = error

    def snapshot(self) -> TradingSessionSnapshot:
        self.snapshot_reads += 1
        return self._snapshot

    def enable(self) -> EnableTradingResult:
        self.enables += 1
        if self._enable_error is not None:
            raise self._enable_error
        if self._enable_result is None:
            # The default is a *successful* enable, and it also updates the
            # snapshot: a fake whose `enable()` left `snapshot().enabled`
            # False would let a caller's "did it turn on?" assertion pass for
            # the wrong reason.
            self.set_enabled(enabled=True)
            return EnableTradingResult(
                enabled=True,
                block_reason=None,
                reconciled_positions=(),
                reconciled_open_orders=(),
            )
        if self._enable_result.enabled:
            self.set_enabled(enabled=True)
        return self._enable_result

    def disable(self) -> None:
        self.disables += 1
        self.set_enabled(enabled=False)

    def emergency_stop(self) -> EmergencyStopResult:
        self.emergency_stops += 1
        if self._stop_error is not None:
            # Raised *before* the state changes: a stop that failed on the
            # network did not disable anything, and a fake that turned trading
            # off anyway would let a caller's "did it recover?" assertion pass
            # for the wrong reason.
            raise self._stop_error
        self.set_enabled(enabled=False)
        if self._stop_result is None:
            return EmergencyStopResult(
                trading_disabled=_stopped("disabled"),
                orders_cancelled=_stopped("no open orders"),
                positions_closed=_stopped("no open positions"),
                final_state_confirmed=True,
            )
        return self._stop_result
