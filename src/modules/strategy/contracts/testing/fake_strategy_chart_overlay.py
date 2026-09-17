"""`FakeStrategyChartOverlay` — `IStrategyChartOverlay`'s verified fake.

A test scripts what one config draws; nothing here replays a strategy or
touches `BaseStrategy`.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_overlay import (
    StrategyOverlay,
)

_EMPTY = StrategyOverlay(lines=(), zones=())


class FakeStrategyChartOverlay(IStrategyChartOverlay):
    def __init__(self, overlay: StrategyOverlay = _EMPTY) -> None:
        self._overlay = overlay
        self.reads = 0
        #: The arguments of the most recent call, for a test asserting
        #: what was asked rather than only what came back.
        self.last_call: tuple[LiveStrategyConfig, tuple[MarketData, ...]] | None = None

    def script(self, overlay: StrategyOverlay) -> None:
        self._overlay = overlay

    def overlay_for(
        self, config: LiveStrategyConfig, candles: Sequence[MarketData]
    ) -> StrategyOverlay:
        self.reads += 1
        self.last_call = (config, tuple(candles))
        return self._overlay
