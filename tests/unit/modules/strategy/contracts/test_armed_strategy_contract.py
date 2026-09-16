"""Both implementations of `IArmedStrategy` against the same contract.

HLD §10.3 rule 2: a fake that has never been run against the real
implementation's contract is a second implementation of nothing. `FakeArmedStrategy`
and `LiveStrategySession` inherit one suite here, so a guarantee a consumer
relies on cannot hold in the fake and fail in production.

The session needs a `LiveStrategyFactory` to arm, and this suite hands it a
stand-in rather than the real one on purpose: the real factory reaches four
`trading` ports to build an engine, and none of that is what these four
assertions are about. The stand-in is named for what it substitutes and its
one method matches `LiveStrategyFactory.build()`'s signature — the shape
`testing-rule.md` §2 asks for, rather than a `Mock` answering whatever the
session happens to call.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_armed_strategy import (
    IArmedStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    ArmedStrategyContract,
    FakeArmedStrategy,
)


class _EngineBuildingFactory:
    """Stands in for `LiveStrategyFactory`: one `build()`, returning the
    `(engine, coordinator)` pair the session stores.

    The two objects are `Mock()`s and that is not the CS-001 mistake: the
    session only *holds* them and forwards ticks, so what this suite needs
    from them is existence — `engine_running` is `self._engine is not None`.
    The thing whose shape matters, the factory, is written out.
    """

    def build(self, config: LiveStrategyConfig) -> tuple[object, object]:
        engine = Mock()
        engine.on_tick.return_value = None
        return engine, Mock()


class TestTheFake(ArmedStrategyContract):
    @pytest.fixture
    def impl(self) -> IArmedStrategy:
        return FakeArmedStrategy()

    @pytest.fixture
    def arm(self, impl: FakeArmedStrategy):
        return lambda config: impl.seed(config)


class TestTheLiveSession(ArmedStrategyContract):
    @pytest.fixture
    def impl(self) -> IArmedStrategy:
        return LiveStrategySession(_EngineBuildingFactory())  # type: ignore[arg-type]

    @pytest.fixture
    def arm(self, impl: LiveStrategySession):
        return impl.arm
