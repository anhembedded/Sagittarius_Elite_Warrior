"""The contract suite for `ITradingSession` (HLD §10.3).

Five guarantees, all of them things a measured consumer depends on (rule 2 —
a guarantee no consumer needs is not in the suite):

1. `snapshot()` reports the session's three facts;
2. it is a **snapshot** — the value a caller holds does not change underneath
   them when the session does. Four presentation files used to read the
   mutable service directly, which is the defect this port exists to close;
3. a successful `ensure_ready()` is visible in the next snapshot — a caller
   asking "did it open?" must not have to take the result's word for it
   (`EPIC-034C`: there is no `disable()`; the session only closes by Emergency
   Stop);
4. `emergency_stop()` leaves the session closed whatever its three steps
   reported. A partial stop is a real outcome, but "trading still on" is not
   one of its forms;
5. the **symbol lease** (`EPIC-025` PR 2.1f): claiming is idempotent for its
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
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistration,
)

#: How a subclass puts its implementation into a known session state.
type GivenSession = Callable[[TradingSessionSnapshot], None]


class SymbolLeaseContract:
    """The lease half, on its own so an implementation can run **just** this.

    @details `TradingSessionContract` needs `ensure_ready()`, which needs the real
    `EnsureSessionReadyCommandHandler` behind a dispatcher — which is why the real
    `TradingSessionService` has never run the full suite (that file's own
    docstring records it). The lease needs none of that: `claim_symbol` and
    `release_symbol` go straight to `TradingSessionState`. Splitting it out is
    what lets the **real** implementation prove these guarantees today
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

        impl.emergency_stop()

        assert held.enabled is True
        assert held.known_open_symbols == ("BTCUSDT",)

    def test_a_successful_open_is_visible_in_the_next_snapshot(
        self, impl: ITradingSession, given_session: GivenSession
    ) -> None:
        given_session(
            TradingSessionSnapshot(
                enabled=False, orders_sent_this_session=0, known_open_symbols=()
            )
        )

        result = impl.ensure_ready()

        if result.ready:
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


def contract_registration(owner_id: str = "bot-1") -> OwnerBudgetRegistration:
    """A registration that fits the default caps, for the suites below."""
    return OwnerBudgetRegistration(
        owner_id=owner_id,
        tag="a3f9c1",
        symbol="BTCUSDT",
        run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
        budget=OwnerBudget(
            max_open_orders=10,
            max_exposure_quote=Decimal(1000),
            min_order_spacing=timedelta(milliseconds=250),
            max_orders_per_window=60,
            window=timedelta(minutes=1),
        ),
    )


class OwnerBudgetContract:
    """`EPIC-029` ADR D6 — what every `ITradingSession` promises about
    budgets without a venue behind it: none while trading is off, and
    clearing never refuses."""

    @pytest.fixture
    def impl(self) -> ITradingSession:
        raise NotImplementedError(
            "an OwnerBudgetContract subclass must provide an `impl` fixture"
        )

    def test_a_budget_is_refused_while_the_session_is_closed(
        self, impl: ITradingSession
    ) -> None:
        result = impl.register_owner_budget(contract_registration())

        assert result.refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF
        assert result.registered is False

    def test_clearing_a_budget_nobody_holds_is_a_no_op(
        self, impl: ITradingSession
    ) -> None:
        impl.clear_owner_budget("nobody")

    def test_nobody_holds_a_symbol_nobody_claimed(self, impl: ITradingSession) -> None:
        assert impl.lease_holder("BTCUSDT") is None

    def test_the_holder_is_the_owner_that_claimed(self, impl: ITradingSession) -> None:
        impl.claim_symbol("BTCUSDT", "strategy")

        assert impl.lease_holder("BTCUSDT") == "strategy"
        assert impl.lease_holder("ETHUSDT") is None

    def test_a_refused_claim_leaves_the_first_owner_the_holder(
        self, impl: ITradingSession
    ) -> None:
        impl.claim_symbol("BTCUSDT", "strategy")
        impl.claim_symbol("BTCUSDT", "someone_else")

        assert impl.lease_holder("BTCUSDT") == "strategy"

    def test_releasing_and_re_claiming_move_the_holder(
        self, impl: ITradingSession
    ) -> None:
        impl.claim_symbol("BTCUSDT", "strategy")
        impl.claim_symbol("ETHUSDT", "strategy")

        assert impl.lease_holder("BTCUSDT") is None
        assert impl.lease_holder("ETHUSDT") == "strategy"
        impl.release_symbol("ETHUSDT", "strategy")
        assert impl.lease_holder("ETHUSDT") is None

    def test_reading_the_holder_claims_nothing(self, impl: ITradingSession) -> None:
        impl.lease_holder("BTCUSDT")

        assert impl.claim_symbol("BTCUSDT", "someone_else") is True
