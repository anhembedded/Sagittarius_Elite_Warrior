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
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing.contract_strategy_chart_overlay import (
    _a_candle,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
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


def test_the_real_service_colours_a_strategys_lines_by_the_series_it_names() -> None:
    """`BOT-161`: the strategy names its lines' series and the service maps
    them through the series table. Without that step every line would fall
    back to the generic palette (review of PR #387)."""
    registry = StrategyRegistry()
    registry.register("ema_trend_pullback", EmaTrendPullbackStrategy)
    config = LiveStrategyConfig(
        strategy_key="ema_trend_pullback",
        symbol="BTCUSDT",
        interval="1m",
        strategy_params={"ema_long_len": 20, "ema_entry_len": 10},
    )
    candles = [_a_candle(index, 100.0 + index) for index in range(40)]

    overlay = StrategyChartOverlayService(registry).overlay_for(config, candles)

    colours = {line.name: line.colour for line in overlay.lines}
    assert colours == {
        EmaTrendPullbackStrategy.EMA_LONG_KEY: "#f6465d",
        EmaTrendPullbackStrategy.EMA_ENTRY_KEY: "#2962ff",
    }
