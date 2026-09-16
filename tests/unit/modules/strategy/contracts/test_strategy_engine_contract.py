"""`IStrategyEngine`'s contract, run against both implementations.

`EPIC-025` PR 3.1b's port. The fake pair and the real
`StrategyEngineFactory`-over-`StrategyRegistry` answer the same suite, which is
the guarantee HLD §10.3 rule 1 asks of a published port: the backtest handlers
test against the fake, so the fake must not be able to promise more than the real
engine does.

The real side needs no container and no network — `StrategyRegistry` is an
in-memory dict of strategy classes, and the publisher is a recorder. `BOT-042D`'s
commit-versus-peek asymmetry is therefore exercised against the **real**
indicator state, which is the part a fake could most easily get wrong.
"""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_engine_factory import (
    StrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_engine import (
    IStrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing.contract_strategy_engine import (
    StrategyEngineContract,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing.fake_strategy_engine import (
    FakeStrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)


class _RecordingPublisher:
    """`IEventPublisher`'s one method, recording instead of emitting.

    A `core/` port owned by nobody, which `test_no_foreign_port_is_mocked.py`
    permits substituting — and derived from the interface rather than from the
    calls the engine happens to make, per `CS-001`.
    """

    def __init__(self) -> None:
        self.published: list[Any] = []

    def publish(self, event: Any) -> None:
        self.published.append(event)


class TestFakeStrategyEngine(StrategyEngineContract):
    @pytest.fixture
    def factory(self) -> IStrategyEngineFactory:
        fake = FakeStrategyEngineFactory()
        fake.refuses("no_such_strategy_anywhere")
        return fake


class TestTheRealFactoryOverTheRealRegistry(StrategyEngineContract):
    @pytest.fixture
    def factory(self) -> IStrategyEngineFactory:
        registry = StrategyRegistry()
        registry.register("ema_crossover", EmaCrossoverStrategy)
        return StrategyEngineFactory(registry, _RecordingPublisher())


def test_the_fake_factory_records_what_was_asked_for() -> None:
    """The fake's own helper, exercised — `test_fake_helpers_are_verified.py`
    (from `BUG-120`) requires that anything a fake adds beyond its port is used
    by its module's own tests, because a helper nobody drives can be hard-coded
    to a convenient answer and stay green."""
    fake = FakeStrategyEngineFactory()

    fake.build("ema_crossover", {"fast_period": 5})
    fake.build("support_resistance")

    assert fake.built == [
        ("ema_crossover", {"fast_period": 5}),
        ("support_resistance", None),
    ]
    assert len(fake.engines) == 2


def test_the_fake_engine_records_every_candle_and_its_position_side() -> None:
    """`seen` is the other helper, and it is what lets a handler's test assert
    the engine was told the *current position* — the field `BOT-110` added and
    which a handler can silently stop passing."""
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
        PositionSide,
    )

    fake = FakeStrategyEngineFactory()
    engine = fake.build("ema_crossover")

    engine.on_tick(candle(0, close=100.0), PositionSide.LONG)
    engine.on_forming_bar_tick(candle(1, close=101.0, is_closed=False))

    assert [side for _candle, side in engine.seen] == [PositionSide.LONG, None]
    assert engine.committed == 1, "the forming bar must not have committed"
