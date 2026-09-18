"""`IStrategyChartOverlayReader` — trading's own view of an armed strategy's
chart lines and trend zones, without naming the module that computes them.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8 — see `i_armed_strategy_reader.py` in this package for the full boot-order
reasoning.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_chart_overlay import (
    StrategyOverlay,
)


class IStrategyChartOverlayReader(ABC):
    """Replays `config`'s strategy over `candles` and returns what to draw."""

    @abstractmethod
    def overlay_for(
        self, config: ArmedStrategyConfig, candles: Sequence[MarketData]
    ) -> StrategyOverlay:
        """@details Thread-safe: the implementation must be pure over its
        arguments and must not touch a shared session's state. Returns an
        empty `StrategyOverlay` (never raises) when `config` names no
        registered strategy or `candles` is empty."""
        ...
