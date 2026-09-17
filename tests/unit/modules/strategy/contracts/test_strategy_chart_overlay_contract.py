"""Both implementations of `IStrategyChartOverlay` against the same contract.

HLD §10.3 rule 2: `FakeStrategyChartOverlay` and `StrategyChartOverlayService`
inherit one suite here, so "nothing to draw is an empty overlay, never an
exception" cannot hold in the fake and fail in the real service.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
    StrategyChartOverlayService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_overlay import (
    OverlayLine,
    StrategyOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeStrategyChartOverlay,
    StrategyChartOverlayContract,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)


class TestTheFake(StrategyChartOverlayContract):
    @pytest.fixture
    def impl(self) -> IStrategyChartOverlay:
        return FakeStrategyChartOverlay()


class TestTheRealService(StrategyChartOverlayContract):
    @pytest.fixture
    def impl(self) -> IStrategyChartOverlay:
        registry = StrategyRegistry()
        registry.register(self.a_key, EmaCrossoverStrategy)
        return StrategyChartOverlayService(registry)


def test_the_fakes_scripted_overlay_is_what_the_next_read_returns() -> None:
    """`script()` is the fake's own extra helper, beside what
    `IStrategyChartOverlay` declares — `tests/unit/architecture/
    test_fake_helpers_are_verified.py` needs it exercised here."""
    overlay = StrategyOverlay(
        lines=(OverlayLine("ema", (0.0,), (1.0,), "#fff", 2),), zones=()
    )
    fake = FakeStrategyChartOverlay()
    fake.script(overlay)

    result = fake.overlay_for(
        LiveStrategyConfig(
            strategy_key="ema_crossover", symbol="BTCUSDT", interval="1m"
        ),
        [],
    )

    assert result is overlay
