"""`StrategyChartOverlayReaderAdapter` — implements trading's
`IStrategyChartOverlayReader` by wrapping `strategy`'s own, unchanged
`IStrategyChartOverlay`.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8. Bound in `StrategyModule.register()` (`composition/port_bindings.py`).
`MarketData` is already `core`-owned and neutral, so `candles` passes
straight through; only the config argument and the `StrategyOverlay`
result need field-for-field translation.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.live_strategy_config_translation import (
    to_live_strategy_config,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_chart_overlay_reader import (
    IStrategyChartOverlayReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_chart_overlay import (
    OverlayLine as TradingOverlayLine,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_chart_overlay import (
    StrategyOverlay as TradingStrategyOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_chart_overlay import (
    TrendZone as TradingTrendZone,
)


class StrategyChartOverlayReaderAdapter(IStrategyChartOverlayReader):
    """Translates a chart-overlay replay across the trading/strategy boundary."""

    def __init__(self, chart_overlay: IStrategyChartOverlay) -> None:
        self._chart_overlay = chart_overlay

    def overlay_for(
        self, config: ArmedStrategyConfig, candles: Sequence[MarketData]
    ) -> TradingStrategyOverlay:
        overlay = self._chart_overlay.overlay_for(
            to_live_strategy_config(config), candles
        )
        return TradingStrategyOverlay(
            lines=tuple(
                TradingOverlayLine(
                    name=line.name,
                    x=line.x,
                    y=line.y,
                    colour=line.colour,
                    width=line.width,
                )
                for line in overlay.lines
            ),
            zones=tuple(
                TradingTrendZone(
                    start=zone.start,
                    end=zone.end,
                    colour=zone.colour,
                    opacity=zone.opacity,
                )
                for zone in overlay.zones
            ),
        )
