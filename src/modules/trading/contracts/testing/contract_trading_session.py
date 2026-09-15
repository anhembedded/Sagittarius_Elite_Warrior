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
   one of its forms.

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


class TradingSessionContract:
    """Inherit this, provide `impl` and `given_session`. Both must pass it."""

    @pytest.fixture
    def impl(self) -> ITradingSession:
        raise NotImplementedError(
            "a TradingSessionContract subclass must provide an `impl` fixture"
        )

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
