"""`EPIC-022B` — `ArmStrategyCommand` / `DisarmStrategyCommand`.

These two handlers exist for their refusals as much as their happy paths:
they are where the epic's two safety rules (§4.1 "no swap while trading is
on", and the arming side of "no enable without a strategy") actually live.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyBlockReason,
    ArmStrategyCommand,
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyBlockReason,
    DisarmStrategyCommand,
    DisarmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)

_KEY = "ema_crossover"


def _session() -> LiveStrategySession:
    """A real `LiveStrategySession` over a real `StrategyRegistry`, with
    only the two network-facing collaborators (`ICommandDispatcher`,
    `ITradingAccountReader`) mocked.

    Deliberately not a `Mock()` session: the parameter-validation path
    under test *is* `BaseStrategy.__init__` raising, and a mock strategy
    accepts every parameter name in existence — the test would pass
    against a handler that validated nothing at all (`ONBOARDING.md` §4,
    the `BUG-013` trap).
    """
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
        LiveStrategyFactory,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
        StrategyRegistry,
    )

    registry = StrategyRegistry()
    registry.register(_KEY, EmaCrossoverStrategy)
    factory = LiveStrategyFactory(registry, Mock(), Mock(), Mock(), Mock())
    return LiveStrategySession(factory)


def _config(**overrides) -> LiveStrategyConfig:
    values = {
        "strategy_key": _KEY,
        "symbol": "BTCUSDT",
        "interval": "1m",
    }
    values.update(overrides)
    return LiveStrategyConfig(**values)


def test_arming_a_valid_config_arms_the_session() -> None:
    session, state = _session(), FakeTradingSession()
    handler = ArmStrategyCommandHandler(session, state)

    result = handler.execute(ArmStrategyCommand(_config()))

    assert result.armed is True
    assert result.block_reason is None
    assert session.is_armed is True


def test_declared_parameters_reach_the_strategy() -> None:
    """`build_engine` has always accepted `params`, and `boot()` never
    passed them — arming has to, or the picker's "Thông số Chiến lược"
    form would be decorative."""
    session, state = _session(), FakeTradingSession()
    handler = ArmStrategyCommandHandler(session, state)

    result = handler.execute(
        ArmStrategyCommand(_config(strategy_params={"fast_period": 5}))
    )

    assert result.armed is True
    assert session.config is not None
    assert session.config.strategy_params["fast_period"] == 5


def test_refuses_to_swap_the_strategy_while_trading_is_on() -> None:
    """`EPIC-022` §4.1 — the incoming strategy knows nothing about a
    position already on the exchange, and the outgoing strategy's exit
    signal would never arrive."""
    session, state = _session(), FakeTradingSession()
    handler = ArmStrategyCommandHandler(session, state)
    handler.execute(ArmStrategyCommand(_config()))
    first_generation = session.generation
    state.set_enabled(enabled=True)

    result = handler.execute(
        ArmStrategyCommand(_config(strategy_params={"fast_period": 9}))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.TRADING_IS_ENABLED
    assert session.generation == first_generation


def test_an_unknown_strategy_key_is_named_not_crashed_on() -> None:
    session, state = _session(), FakeTradingSession()
    handler = ArmStrategyCommandHandler(session, state)

    result = handler.execute(
        ArmStrategyCommand(_config(strategy_key="no_such_strategy"))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.STRATEGY_NOT_FOUND
    assert session.is_armed is False


def test_an_undeclared_parameter_is_reported_with_the_strategys_own_words() -> None:
    """The strategy is the validator; the handler only relays. Asserting
    the parameter name appears proves the message was not replaced by a
    generic one the user cannot act on."""
    session, state = _session(), FakeTradingSession()
    handler = ArmStrategyCommandHandler(session, state)

    result = handler.execute(
        ArmStrategyCommand(_config(strategy_params={"not_a_real_param": 1}))
    )

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.INVALID_PARAMS
    assert "not_a_real_param" in (result.error_message or "")
    assert session.is_armed is False


@pytest.mark.parametrize("missing", ["symbol", "interval"])
def test_a_missing_symbol_or_interval_is_refused_never_guessed(missing: str) -> None:
    """`BUG-085`: a wrong interval is a wrong strategy. Defaulting to
    "any interval" would silently feed one engine two timeframes."""
    session, state = _session(), FakeTradingSession()
    handler = ArmStrategyCommandHandler(session, state)

    result = handler.execute(ArmStrategyCommand(_config(**{missing: ""})))

    assert result.armed is False
    assert result.block_reason is ArmStrategyBlockReason.MISSING_SYMBOL_OR_INTERVAL
    assert session.is_armed is False


def test_disarming_clears_the_session() -> None:
    session, state = _session(), FakeTradingSession()
    ArmStrategyCommandHandler(session, state).execute(ArmStrategyCommand(_config()))

    result = DisarmStrategyCommandHandler(session, state).execute(
        DisarmStrategyCommand()
    )

    assert result.disarmed is True
    assert session.is_armed is False


def test_refuses_to_disarm_while_trading_is_on() -> None:
    """Disarming while trading is on would leave any open position with
    no strategy planning its exit — `DisarmStrategyCommandHandler` still
    refuses this direction even though `EnableTradingCommand` itself no
    longer requires an armed strategy to reach "trading on" at all
    (`BUG-112`)."""
    session, state = _session(), FakeTradingSession()
    ArmStrategyCommandHandler(session, state).execute(ArmStrategyCommand(_config()))
    state.set_enabled(enabled=True)

    result = DisarmStrategyCommandHandler(session, state).execute(
        DisarmStrategyCommand()
    )

    assert result.disarmed is False
    assert result.block_reason is DisarmStrategyBlockReason.TRADING_IS_ENABLED
    assert session.is_armed is True
