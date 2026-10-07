"""`EPIC-034C` — arming starts trading, and an open position still refuses.

@details The Enable switch is gone, so `ArmStrategyCommandHandler` opens the
venue's order session itself (reconciling the account first) and
`DisarmStrategyCommandHandler` no longer waits for trading to be off. The rule
that refused both while trading was on (`EPIC-022` §4.1) is restated as its
cause: a position open on the strategy's symbol. The remaining arm and disarm
behaviour is `test_arm_strategy.py`'s.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyBlockReason,
    DisarmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.strategy.application.use_cases.arm_strategy_builders import (
    FUTURES,
    arm_command,
    arm_handler,
    config_for,
    disarm_handler,
    new_session,
)


def _holding(symbol: str) -> TradingSessionSnapshot:
    """An open session in which the app has a position on `symbol`."""
    return TradingSessionSnapshot(
        enabled=True, orders_sent_this_session=1, known_open_symbols=(symbol,)
    )


def test_arming_opens_the_order_session_itself() -> None:
    """`EPIC-034C` — no switch was turned on first: arming reconciles the
    account and opens the session, once."""
    session, state = new_session(), FakeTradingSession()

    result = arm_handler(session, state).execute(arm_command(config_for()))

    assert result.armed is True
    assert state.snapshot().enabled is True
    assert state.ready_requests == 1


def test_a_session_that_will_not_open_refuses_the_arm_with_the_reason_in_words() -> (
    None
):
    """A position the app did not open (or a connection that is not ready)
    refuses before anything is claimed or armed."""
    session, state = new_session(), FakeTradingSession()
    state.ready_answers(
        SessionReadyResult(
            ready=False,
            block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
    )

    result = arm_handler(session, state).execute(arm_command(config_for()))

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.SESSION_NOT_READY
    assert "unexpected open positions" in (result.error_message or "")
    assert session.is_armed is False
    assert state.claim_symbol("BTCUSDT", "someone_else") is True  # no lease taken


def test_a_config_refused_for_its_own_fields_does_not_open_the_session() -> None:
    """The refusals that cost nothing run first; a doomed arm reads no account."""
    session, state = new_session(), FakeTradingSession()

    result = arm_handler(session, state).execute(arm_command(config_for(symbol="")))

    assert result.block_reason is ArmStrategyBlockReason.MISSING_SYMBOL_OR_INTERVAL
    assert state.ready_requests == 0


def test_refuses_to_swap_the_strategy_while_a_position_is_open_on_its_symbol() -> None:
    """`EPIC-022` §4.1 — the incoming strategy knows nothing about a
    position already on the exchange, and the outgoing strategy's exit
    signal would never arrive. Restated by `EPIC-034C`: with no switch the
    open position itself refuses."""
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)
    handler.execute(arm_command(config_for()))
    first_generation = session.generation
    state.answer_with(_holding("BTCUSDT"))

    result = handler.execute(
        arm_command(config_for(strategy_params={"fast_period": 9}))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.POSITION_OPEN
    assert session.generation == first_generation


def test_a_position_on_another_symbol_does_not_refuse_the_arm() -> None:
    session, state = new_session(), FakeTradingSession()
    state.answer_with(_holding("ETHUSDT"))

    result = arm_handler(session, state).execute(arm_command(config_for()))

    assert result.armed is True


def test_an_open_session_with_no_position_does_not_refuse_the_arm() -> None:
    """The session stays open after the first action; that alone refuses
    nothing (it refused every arm after a bot's Start before this rule)."""
    session, state = new_session(), FakeTradingSession()
    state.set_enabled(enabled=True)

    result = arm_handler(session, state).execute(arm_command(config_for()))

    assert result.armed is True


def test_refuses_to_disarm_while_a_position_is_open_on_the_strategys_symbol() -> None:
    """Disarming with a position open would leave it with no strategy planning
    its exit; `EmergencyStopCommand` is the way out (`EPIC-034C` restates the
    rule that refused this while trading was on)."""
    session, state = new_session(), FakeTradingSession()
    arm_handler(session, state).execute(arm_command(config_for()))
    state.answer_with(_holding("BTCUSDT"))

    result = disarm_handler(session, state).execute(
        DisarmStrategyCommand(venue=FUTURES)
    )

    assert result.disarmed is False
    assert result.block_reason is DisarmStrategyBlockReason.POSITION_OPEN
    assert session.is_armed is True


def test_disarming_is_allowed_while_the_session_is_open_and_flat() -> None:
    session, state = new_session(), FakeTradingSession()
    arm_handler(session, state).execute(arm_command(config_for()))
    assert state.snapshot().enabled is True

    result = disarm_handler(session, state).execute(
        DisarmStrategyCommand(venue=FUTURES)
    )

    assert result.disarmed is True


def test_a_closed_session_knows_no_positions_so_it_never_refuses_a_disarm() -> None:
    """After an Emergency Stop the stream is stopped and `known_open_symbols`
    may be stale; only an open session's record refuses."""
    session, state = new_session(), FakeTradingSession()
    arm_handler(session, state).execute(arm_command(config_for()))
    state.answer_with(
        TradingSessionSnapshot(
            enabled=False,
            orders_sent_this_session=1,
            known_open_symbols=("BTCUSDT",),
        )
    )

    result = disarm_handler(session, state).execute(
        DisarmStrategyCommand(venue=FUTURES)
    )

    assert result.disarmed is True
