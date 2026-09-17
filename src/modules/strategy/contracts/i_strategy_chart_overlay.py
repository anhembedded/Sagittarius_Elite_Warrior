"""`IStrategyChartOverlay` — an armed strategy's chart lines and trend
zones, computed inside `strategy` (`EPIC-025`
`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`,
O1).

@details The overlay's compute functions (`strategy_overlay/`) were always
Qt-free, but publishing them alone would have left the caller building the
throwaway strategy instance itself — the exact reason it needed
`type[BaseStrategy]` from the registry. This port keeps the whole
replay (registry lookup, instantiation, `build_indicators()`, colour
assignment) on the side that owns the domain class, and answers in data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_overlay import (
    StrategyOverlay,
)


class IStrategyChartOverlay(ABC):
    """Replays `config`'s strategy over `candles` and returns what to draw."""

    @abstractmethod
    def overlay_for(
        self, config: LiveStrategyConfig, candles: Sequence[MarketData]
    ) -> StrategyOverlay:
        """@details Thread-safe: `backtest`'s coordinator calls this off the
        UI thread, under its own action id, so the implementation must be
        pure over its arguments and must not touch a shared session's state.
        Returns an empty `StrategyOverlay` (never raises) when `config`
        names no registered strategy or `candles` is empty — the caller
        already treats "nothing to draw" as a normal state, not an error.
        """
        ...
