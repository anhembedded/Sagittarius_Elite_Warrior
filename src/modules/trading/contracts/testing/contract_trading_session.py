"""The contract suite for `ITradingSession` (HLD §10.3).

Five guarantees, all of them things a measured consumer depends on (rule 2 —
a guarantee no consumer needs is not in the suite):

1. `snapshot()` reports the session's three facts;
2. it is a **snapshot** — the value a caller holds does not change underneath
   them when the session does. Four presentation files used to read the
   mutable service directly, which is the defect this port exists to close;
3. `disable()` always succeeds and is visible in the next snapshot. It cannot
   refuse, which is why it has no result type;
4. a successful `enable()` is visible in the next snapshot — a caller asking
   "did it turn on?" must not have to take the result's word for it;
5. `emergency_stop()` leaves the session disabled whatever its three steps
   reported. A partial stop is a real outcome, but "trading still on" is not
   one of its forms;
6. the **symbol lease** (`EPIC-025` PR 2.1f): claiming is idempotent for its
   own owner, one owner holds one symbol so a second claim releases the first,
   releasing is a no-op for a symbol you do not hold, and one owner can never
   release another's claim. The last of those is the one that matters — the
   whole point of the lease is that a manual order path cannot clear the
   strategy's claim to let itself through — and the second is what stops a
   re-armed strategy stranding its old symbol.

**One hook.** A subclass supplies `given_session`, which puts the session into
a known state: the fake is told, and the real `TradingSessionService` is told
by enabling through its own command handler.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
    TradingSessionSnapshot,
)

#: How a subclass puts its implementation into a known session state.
type GivenSession = Callable[[TradingSessionSnapshot], None]


class SymbolLeaseContract:
    """The lease half, on its own so an implementation can run **just** this.

    @details `TradingSessionContract` needs `enable()`, which needs the real
    `EnableTradingCommandHandler` behind a dispatcher — which is why the real
    `TradingSessionService` has never run the full suite (that file's own
    docstring records it). The lease needs none of that: `claim_symbol` and
    `release_symbol` go straight to `TradingSessionState`. Splitting it out is
    what lets the **real** implementation prove these seven guarantees today
    instead of inheriting a deferral that has nothing to do with them
    (HLD §10.3 rule 3 — both implementations run the suite).
    """

    @pytest.fixture
    def impl(self) -> ITradingSession:
        raise NotImplementedError(
            "a SymbolLeaseContract subclass must provide an `impl` fixture"
        )

    # ------------------------------------------------------------------ #
    # The symbol lease (`EPIC-025` PR 2.1f)
    # ------------------------------------------------------------------ #

    def test_a_claim_is_granted_on_a_free_symbol(self, impl: ITradingSession) -> None:
        assert impl.claim_symbol("BTCUSDT", "strategy") is True

    def test_re_claiming_your_own_symbol_is_granted(
        self, impl: ITradingSession
    ) -> None:
        """Arming twice onto the same symbol must not refuse the second time —
        `LiveStrategySession.arm()` re-arms without disarming first."""
        impl.claim_symbol("BTCUSDT", "strategy")

        assert impl.claim_symbol("BTCUSDT", "strategy") is True

    def test_another_owner_is_refused_and_changes_nothing(
        self, impl: ITradingSession
    ) -> None:
        impl.claim_symbol("BTCUSDT", "strategy")

        assert impl.claim_symbol("BTCUSDT", "someone_else") is False
        # And the first owner still holds it: a refused claim that had quietly
        # taken the lease anyway would be the worst of both answers.
        assert impl.claim_symbol("BTCUSDT", "strategy") is True

    def test_claiming_a_second_symbol_releases_the_first(
        self, impl: ITradingSession
    ) -> None:
        """One symbol per owner. Re-arming a strategy onto another symbol must
        not leave the old one claimed by a strategy nobody is running — which
        a manual order on that old symbol would then still be refused for."""
        impl.claim_symbol("BTCUSDT", "strategy")
        impl.claim_symbol("ETHUSDT", "strategy")

        # BTCUSDT is free again, so a different owner may take it.
        assert impl.claim_symbol("BTCUSDT", "someone_else") is True

    def test_releasing_frees_the_symbol(self, impl: ITradingSession) -> None:
        impl.claim_symbol("BTCUSDT", "strategy")

        impl.release_symbol("BTCUSDT", "strategy")

        assert impl.claim_symbol("BTCUSDT", "someone_else") is True

    def test_releasing_a_symbol_you_never_claimed_is_a_no_op(
        self, impl: ITradingSession
    ) -> None:
        """A disarm with nothing armed calls this, so refusing would make every
        caller check first."""
        impl.release_symbol("BTCUSDT", "strategy")

        assert impl.claim_symbol("BTCUSDT", "someone_else") is True

    def test_one_owner_cannot_release_anothers_claim(
        self, impl: ITradingSession
    ) -> None:
        """The guarantee the lease exists for: a manual order path must not be
        able to clear the strategy's claim to get itself through."""
        impl.claim_symbol("BTCUSDT", "strategy")

        impl.release_symbol("BTCUSDT", "someone_else")

        assert impl.claim_symbol("BTCUSDT", "someone_else") is False


class TradingSessionContract(SymbolLeaseContract):
    """Inherit this, provide `impl` and `given_session`. Both implementations
    must pass it — and it includes `SymbolLeaseContract`, so a subclass that
    runs this runs the lease guarantees too."""

    @pytest.fixture
    def given_session(self) -> GivenSession:
        raise NotImplementedError(
            "a TradingSessionContract subclass must provide a `given_session` "
            "fixture that puts its implementation into a known state"
        )

    def test_the_snapshot_reports_the_three_facts(
        self, impl: ITradingSession, given_session: GivenSession
    ) -> None:
        given_session(
            TradingSessionSnapshot(
                enabled=True,
                orders_sent_this_session=3,
                known_open_symbols=("BTCUSDT", "ETHUSDT"),
            )
        )

        answer = impl.snapshot()

        assert answer.enabled is True
        assert answer.orders_sent_this_session == 3
        assert answer.known_open_symbols == ("BTCUSDT", "ETHUSDT")

    def test_a_held_snapshot_does_not_change_when_the_session_does(
        self, impl: ITradingSession, given_session: GivenSession
    ) -> None:
        """The whole point of the port. A Presenter that read the mutable
        service saw `known_open_symbols` change under it while the websocket
        thread reconciled positions."""
        given_session(
            TradingSessionSnapshot(
                enabled=True,
                orders_sent_this_session=1,
                known_open_symbols=("BTCUSDT",),
            )
        )
        held = impl.snapshot()

        impl.disable()

        assert held.enabled is True
        assert held.known_open_symbols == ("BTCUSDT",)

    def test_disable_is_visible_in_the_next_snapshot(
        self, impl: ITradingSession, given_session: GivenSession
    ) -> None:
        given_session(
            TradingSessionSnapshot(
                enabled=True, orders_sent_this_session=0, known_open_symbols=()
            )
        )

        impl.disable()

        assert impl.snapshot().enabled is False

    def test_a_successful_enable_is_visible_in_the_next_snapshot(
        self, impl: ITradingSession, given_session: GivenSession
    ) -> None:
        given_session(
            TradingSessionSnapshot(
                enabled=False, orders_sent_this_session=0, known_open_symbols=()
            )
        )

        result = impl.enable()

        if result.enabled:
            assert impl.snapshot().enabled is True

    def test_emergency_stop_leaves_the_session_disabled(
        self, impl: ITradingSession, given_session: GivenSession
    ) -> None:
        given_session(
            TradingSessionSnapshot(
                enabled=True,
                orders_sent_this_session=2,
                known_open_symbols=("BTCUSDT",),
            )
        )

        impl.emergency_stop()

        assert impl.snapshot().enabled is False
