"""`ITradingSession`'s contract, against its verified fake (HLD §10.3).

The real `TradingSessionService` runs the same suite once PR 1.3c moves the
handler registrations into the module: `enable()` needs
`EnableTradingCommandHandler`, which needs the `ExchangeSessionFactory`
instance still shared with `market_data`. Recorded here rather than left as a
silent gap.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingBlockReason,
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_trading_session import (
    GivenSession,
    TradingSessionContract,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)


class TestTheFake(TradingSessionContract):
    @pytest.fixture
    def impl(self) -> FakeTradingSession:
        return FakeTradingSession()

    @pytest.fixture
    def given_session(self, impl: FakeTradingSession) -> GivenSession:
        def seed(snapshot: TradingSessionSnapshot) -> None:
            impl.answer_with(snapshot)

        return seed


class TestTheFakesOwnBookkeeping:
    """`BUG-120` — what the fake adds beyond the port is tested too, because a
    helper nothing verifies is a helper a consumer can assert through while
    asserting nothing."""

    def test_set_enabled_flips_one_flag_and_keeps_the_rest(self) -> None:
        fake = FakeTradingSession(
            TradingSessionSnapshot(
                enabled=False,
                orders_sent_this_session=4,
                known_open_symbols=("BTCUSDT",),
            )
        )

        fake.set_enabled(enabled=True)

        answer = fake.snapshot()
        assert answer.enabled is True
        assert answer.orders_sent_this_session == 4
        assert answer.known_open_symbols == ("BTCUSDT",)

    def test_enable_answers_drives_a_refusal_and_leaves_the_session_off(self) -> None:
        """A blocked enable must not flip the snapshot on — that combination
        (result refused, session enabled) never happens in production, and a
        fake that allowed it would let a caller's error branch pass while the
        success branch was the one running."""
        fake = FakeTradingSession()
        fake.enable_answers(
            EnableTradingResult(
                enabled=False,
                block_reason=EnableTradingBlockReason.CONNECTION_NOT_READY,
                reconciled_positions=(),
                reconciled_open_orders=(),
            )
        )

        result = fake.enable()

        assert result.enabled is False
        assert fake.snapshot().enabled is False
        assert fake.enables == 1

    def test_emergency_stop_answers_drives_a_partial_stop(self) -> None:
        partial = EmergencyStopResult(
            trading_disabled=EmergencyStopStepResult(succeeded=True, detail="off"),
            orders_cancelled=EmergencyStopStepResult(succeeded=False, detail="timeout"),
            positions_closed=EmergencyStopStepResult(succeeded=False, detail="skipped"),
            final_state_confirmed=False,
        )
        fake = FakeTradingSession()
        fake.emergency_stop_answers(partial)

        assert fake.emergency_stop() is partial
        # Still disabled: a partial stop is a real outcome, but "trading left
        # on" is not one of its forms.
        assert fake.snapshot().enabled is False

    def test_the_default_enable_succeeds_and_shows_up(self) -> None:
        """A fake whose `enable()` left the snapshot False would let a
        caller's "did it turn on?" assertion pass for the wrong reason."""
        fake = FakeTradingSession()

        assert fake.enable().enabled is True
        assert fake.snapshot().enabled is True

    def test_it_counts_each_call_separately(self) -> None:
        fake = FakeTradingSession()

        fake.snapshot()
        fake.snapshot()
        fake.disable()

        assert (fake.snapshot_reads, fake.disables, fake.enables) == (2, 1, 0)

    def test_enable_raises_produces_a_failure_the_caller_must_handle(self) -> None:
        """`EPIC-025` PR 1.3c-1 — a refusal is a result, but the two network
        round trips behind `enable()` can still fail, and both Presenters carry
        a test that the failure is reported rather than raised at the UI. The
        call is still counted: "it was attempted and blew up" is a different
        fact from "it was never attempted"."""
        fake = FakeTradingSession()
        fake.enable_raises(RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            fake.enable()

        assert fake.enables == 1
        assert fake.snapshot().enabled is False

    def test_emergency_stop_raises_leaves_the_session_as_it_was(self) -> None:
        """A stop that failed on the network disabled nothing. A fake that
        turned trading off anyway would let a caller's "did it recover?"
        assertion pass for the wrong reason."""
        fake = FakeTradingSession()
        fake.set_enabled(enabled=True)
        fake.emergency_stop_raises(RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            fake.emergency_stop()

        assert fake.emergency_stops == 1
        assert fake.snapshot().enabled is True
