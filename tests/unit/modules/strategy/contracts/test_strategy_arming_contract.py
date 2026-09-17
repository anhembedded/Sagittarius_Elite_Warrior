"""Both implementations of `IStrategyArming` against the same contract.

HLD §10.3 rule 2: `FakeStrategyArming` and `StrategyArmingService` inherit one
suite here, so "a successful arm becomes the saved selection" — moved inside
`ArmStrategyCommandHandler` by `EPIC-025` PR 4.3m — cannot hold in the fake and
fail in the real service.

`_DirectDispatcher` stands in for `EngineCommandDispatcher`: real dispatch by
handler class, no engine `IDispatcher` behind it, because what this suite is
about is `StrategyArmingService`'s own two `dispatch()` calls, not the
engine's routing. `DictConfig` is the engine's own in-memory `IConfig` —
`testing-rule.md` §2 prefers the real, cheap collaborator over a hand-written
double of it.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_arming_service import (
    StrategyArmingService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeStrategyArming,
    StrategyArmingContract,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig

_KEY = "ema_crossover"


class _DirectDispatcher(ICommandDispatcher):
    """Real routing by handler class, over a fixed set registered up front —
    the one thing `StrategyArmingService` needs from `ICommandDispatcher`."""

    def __init__(self, handlers: dict[type, object]) -> None:
        self._handlers = handlers

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self._handlers[handler_class].execute(input_dto)


class TestTheFake(StrategyArmingContract):
    @pytest.fixture
    def impl(self) -> IStrategyArming:
        return FakeStrategyArming()


class TestTheRealService(StrategyArmingContract):
    @pytest.fixture
    def impl(self) -> IStrategyArming:
        registry = StrategyRegistry()
        registry.register(_KEY, EmaCrossoverStrategy)
        # The same stand-in `test_arm_strategy.py::_session()` uses: the
        # config-validation path under test never reaches these four, since
        # `arm()` builds an engine but this suite never dispatches a tick.
        session = LiveStrategySession(
            LiveStrategyFactory(registry, Mock(), Mock(), Mock(), Mock())
        )
        trading_session = FakeTradingSession()
        config_store = LiveStrategyConfigStore(DictConfig())
        dispatcher = _DirectDispatcher(
            {
                ArmStrategyCommandHandler: ArmStrategyCommandHandler(
                    session, trading_session, config_store
                ),
                DisarmStrategyCommandHandler: DisarmStrategyCommandHandler(
                    session, trading_session
                ),
            }
        )
        return StrategyArmingService(dispatcher, config_store)


def test_the_fakes_scripted_arm_result_is_what_arm_answers() -> None:
    """`script_arm()` is the fake's own extra helper, beside what
    `IStrategyArming` declares — `tests/unit/architecture/
    test_fake_helpers_are_verified.py` needs it exercised here."""
    fake = FakeStrategyArming()
    blocked = ArmStrategyResult(armed=False)
    fake.script_arm(blocked)

    result = fake.arm(
        LiveStrategyConfig(strategy_key=_KEY, symbol="BTCUSDT", interval="1m")
    )

    assert result is blocked
    assert fake.saved_selection().is_complete is False


def test_the_fakes_scripted_disarm_result_is_what_disarm_answers() -> None:
    """`script_disarm()` is the fake's own extra helper, exercised the same
    way as `script_arm()` above."""
    fake = FakeStrategyArming()
    refused = DisarmStrategyResult(disarmed=False)
    fake.script_disarm(refused)

    result = fake.disarm()

    assert result is refused
    assert fake.disarm_calls == 1
