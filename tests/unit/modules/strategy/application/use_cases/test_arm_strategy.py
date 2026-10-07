"""`EPIC-022B` — `ArmStrategyCommand` / `DisarmStrategyCommand`.

These two handlers exist for their refusals as much as their happy paths:
they are where the epic's two safety rules (§4.1 "no swap while trading is
on", and the arming side of "no enable without a strategy") actually live.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.strategy.application.use_cases.arm_strategy_builders import (
    FUTURES,
    SHORT_CAPABLE_KEY,
    SPOT,
    arm_command,
    arm_handler,
    arm_spot_command,
    config_for,
    disarm_handler,
    new_session,
    spot_state,
)


def test_arming_a_valid_config_arms_the_session() -> None:
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)

    result = handler.execute(arm_command(config_for()))

    assert result.armed is True
    assert result.block_reason is None
    assert session.is_armed is True


def test_declared_parameters_reach_the_strategy() -> None:
    """`build_engine` has always accepted `params`, and `boot()` never
    passed them — arming has to, or the picker's "Thông số Chiến lược"
    form would be decorative."""
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)

    result = handler.execute(
        arm_command(config_for(strategy_params={"fast_period": 5}))
    )

    assert result.armed is True
    assert session.config is not None
    assert session.config.strategy_params["fast_period"] == 5


def test_an_unknown_strategy_key_is_named_not_crashed_on() -> None:
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)

    result = handler.execute(arm_command(config_for(strategy_key="no_such_strategy")))

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.STRATEGY_NOT_FOUND
    assert session.is_armed is False


def test_an_undeclared_parameter_is_reported_with_the_strategys_own_words() -> None:
    """The strategy is the validator; the handler only relays. Asserting
    the parameter name appears proves the message was not replaced by a
    generic one the user cannot act on."""
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)

    result = handler.execute(
        arm_command(config_for(strategy_params={"not_a_real_param": 1}))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.INVALID_PARAMS
    assert "not_a_real_param" in (result.error_message or "")
    assert session.is_armed is False


@pytest.mark.parametrize("missing", ["symbol", "interval"])
def test_a_missing_symbol_or_interval_is_refused_never_guessed(missing: str) -> None:
    """`BUG-085`: a wrong interval is a wrong strategy. Defaulting to
    "any interval" would silently feed one engine two timeframes."""
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)

    result = handler.execute(arm_command(config_for(**{missing: ""})))

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.MISSING_SYMBOL_OR_INTERVAL
    assert session.is_armed is False


def test_disarming_clears_the_session() -> None:
    session, state = new_session(), FakeTradingSession()
    arm_handler(session, state).execute(arm_command(config_for()))

    result = disarm_handler(session, state).execute(
        DisarmStrategyCommand(venue=FUTURES)
    )

    assert result.disarmed is True
    assert session.is_armed is False


# --------------------------------------------------------------------- #
# The symbol lease (`EPIC-025` PR 2.1f)
# --------------------------------------------------------------------- #


def test_arming_claims_the_symbols_lease() -> None:
    """The claim is what makes `trading` refuse a manual order on the symbol
    this strategy is now watching — the user's decision of 2026-09-09
    (`PRO-003` §4.1.2), enforced on the order path instead of in one screen."""
    session, state = new_session(), FakeTradingSession()

    arm_handler(session, state).execute(arm_command(config_for()))

    # Somebody else can no longer take it, which is the observable form of
    # "the strategy holds it".
    assert state.claim_symbol("BTCUSDT", "someone_else") is False


def test_re_arming_onto_another_symbol_gives_the_first_one_back() -> None:
    """One symbol per owner. Without this, a strategy moved from BTCUSDT to
    ETHUSDT would leave BTCUSDT refused for a strategy nobody is running."""
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)
    handler.execute(arm_command(config_for(symbol="BTCUSDT")))

    handler.execute(arm_command(config_for(symbol="ETHUSDT")))

    assert state.claim_symbol("BTCUSDT", "someone_else") is True
    assert state.claim_symbol("ETHUSDT", "someone_else") is False


def test_a_refused_arming_does_not_keep_the_lease() -> None:
    """The claim happens before the arming, so an arming that then fails has
    to give it back — otherwise an invalid parameter value would leave the
    user's own manual orders refused on a symbol with no strategy on it."""
    session, state = new_session(), FakeTradingSession()
    handler = arm_handler(session, state)

    result = handler.execute(
        arm_command(config_for(strategy_params={"nonexistent_param": 1}))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.INVALID_PARAMS
    assert state.claim_symbol("BTCUSDT", "someone_else") is True


def test_a_symbol_another_owner_holds_is_refused_and_nothing_is_armed() -> None:
    """Unreachable with one armed strategy, and named anyway: `claim_symbol`'s
    contract can refuse, and the handler claims *before* arming so that a
    refusal leaves no half-armed session behind."""
    session, state = new_session(), FakeTradingSession()
    state.claim_symbol("BTCUSDT", "someone_else")

    result = arm_handler(session, state).execute(arm_command(config_for()))

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.SYMBOL_LEASED
    assert session.is_armed is False


def test_disarming_releases_the_lease() -> None:
    session, state = new_session(), FakeTradingSession()
    arm_handler(session, state).execute(arm_command(config_for()))

    disarm_handler(session, state).execute(DisarmStrategyCommand(venue=FUTURES))

    assert state.claim_symbol("BTCUSDT", "someone_else") is True


def test_a_refused_disarm_keeps_the_lease() -> None:
    """A position is open on the strategy's symbol, so the disarm is refused —
    and a lease released anyway would let a manual order onto the symbol of a
    strategy that is still running, which is the exact hazard the lease exists
    for."""
    session, state = new_session(), FakeTradingSession()
    arm_handler(session, state).execute(arm_command(config_for()))
    state.answer_with(
        TradingSessionSnapshot(
            enabled=True, orders_sent_this_session=1, known_open_symbols=("BTCUSDT",)
        )
    )

    result = disarm_handler(session, state).execute(
        DisarmStrategyCommand(venue=FUTURES)
    )

    assert result.disarmed is False
    assert state.claim_symbol("BTCUSDT", "someone_else") is False


# --------------------------------------------------------------------- #
# Spot-only refusals (`EPIC-027N`)
# --------------------------------------------------------------------- #


def test_spot_refuses_a_leverage_other_than_1x() -> None:
    """AC1 — Spot has no margin to lever; a saved config naming anything
    else is refused, never silently clamped to 1x."""
    session, state = new_session(), spot_state()

    result = arm_handler(session, state, SPOT).execute(
        arm_spot_command(config_for(leverage=5.0))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.SPOT_LEVERAGE_NOT_SUPPORTED
    assert session.is_armed is False


def test_spot_arms_at_the_default_1x_leverage() -> None:
    """The refusal above must not fire on the one leverage Spot actually
    supports — a strategy could otherwise never be armed on Spot at all."""
    session, state = new_session(), spot_state()

    result = arm_handler(session, state, SPOT).execute(
        arm_spot_command(config_for(leverage=1.0))
    )

    assert result.armed is True
    assert result.block_reason is None


def test_spot_refuses_a_strategy_that_can_short() -> None:
    """AC2 (ADR O2) — `EmaTrendPullbackStrategy` really does call
    `self.short()`; arming it on Spot would silently drop that half of what
    it does, so it is refused instead."""
    session, state = new_session(), spot_state()

    result = arm_handler(session, state, SPOT).execute(
        arm_spot_command(config_for(strategy_key=SHORT_CAPABLE_KEY, leverage=1.0))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.SPOT_SHORT_NOT_SUPPORTED
    assert session.is_armed is False


def test_spot_arms_a_long_only_strategy_that_cannot_short() -> None:
    """The refusal above must not fire on a strategy that never declares
    `SHORT` — `EmaCrossoverStrategy` is long-only by `BaseStrategy`'s own
    default."""
    session, state = new_session(), spot_state()

    result = arm_handler(session, state, SPOT).execute(
        arm_spot_command(config_for(leverage=1.0))
    )

    assert result.armed is True
    assert result.block_reason is None


def test_spot_refuses_a_non_usdt_quoted_symbol() -> None:
    """AC5 (ADR D9/O4) — Phase 1 Spot trades USDT-quoted pairs only; the
    session limits and sizing are already USDT-denominated."""
    session, state = new_session(), spot_state()

    result = arm_handler(session, state, SPOT).execute(
        arm_spot_command(config_for(symbol="BTCBUSD", leverage=1.0))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.SPOT_QUOTE_ASSET_NOT_SUPPORTED
    assert session.is_armed is False


def test_futures_arming_is_unaffected_by_any_spot_only_refusal() -> None:
    """None of the three Spot checks apply off Spot — a `FakeTradingSession`
    with no market_type set (the Futures-shaped default) must arm a
    SHORT-capable strategy at high leverage on a non-USDT symbol exactly as
    it always could."""
    session, state = new_session(), FakeTradingSession()

    result = arm_handler(session, state).execute(
        arm_command(
            config_for(strategy_key=SHORT_CAPABLE_KEY, symbol="BTCBUSD", leverage=20.0)
        )
    )

    assert result.armed is True
    assert result.block_reason is None
