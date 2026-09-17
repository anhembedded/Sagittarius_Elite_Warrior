"""`StrategyChartOverlayService` — `IStrategyChartOverlay`'s implementation.

@details The throwaway-strategy build and the three `strategy_overlay/`
compute calls, unchanged from `StrategyOverlayCoordinator`'s and
`IndicatorCoordinator`'s own versions — only relocated to the side that
owns `BaseStrategy`, so a caller across the module boundary receives
`OverlayLine`/`TrendZone` instead of building the strategy itself.

@par Why the `ui.strategy_overlay` import is inside `overlay_for()`
Not a stand-in for a missing seam (`code-quality-rule.md` §4's ban is about
that) — this class is bound eagerly in `composition/port_bindings.py`, so a
module-level import here would run the instant `strategy`'s `module.py` is
imported, in every run including a headless `sync`.
`compute_strategy_trend_zones` reaches `support/charting/chart_card/theme.py`
for its colour constants, and that package's `__init__.py` imports the real
`ChartCard` widget — genuinely Qt-heavy, the same shape
`modules/trading/ui/probes.py` documents for a `DEV_PROBE` factory: the lazy
import *is* the mechanism, paid only when a screen actually asks for an
overlay (`tests/unit/architecture/test_module_contribution_laziness.py`).
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
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
    TrendZone,
)

#: Matches `StrategyOverlayCoordinator.redraw()`'s own fallbacks — a line
#: `chart_line_colors()`/`chart_line_widths()` did not name still draws.
_DEFAULT_COLOUR = ""
_DEFAULT_WIDTH = 2


class StrategyChartOverlayService(IStrategyChartOverlay):
    def __init__(self, registry: StrategyRegistry) -> None:
        self._registry = registry

    def overlay_for(
        self, config: LiveStrategyConfig, candles: Sequence[MarketData]
    ) -> StrategyOverlay:
        from Sagittarius_Elite_Warrior.src.modules.strategy.ui.strategy_overlay import (
            assign_strategy_line_colors,
            compute_strategy_indicator_lines,
            compute_strategy_trend_zones,
        )

        strategy_cls = self._registry.available().get(config.strategy_key)
        if strategy_cls is None or not candles:
            return StrategyOverlay(lines=(), zones=())

        strategy = strategy_cls(dict(config.strategy_params))
        raw_lines = compute_strategy_indicator_lines(strategy, candles)
        colours = assign_strategy_line_colors(
            list(raw_lines), strategy.chart_line_colors()
        )
        widths = strategy.chart_line_widths()
        lines = tuple(
            OverlayLine(
                name=name,
                x=tuple(x_data),
                y=tuple(y_data),
                colour=colours.get(name, _DEFAULT_COLOUR),
                width=int(widths.get(name, _DEFAULT_WIDTH)),
            )
            for name, (x_data, y_data) in raw_lines.items()
        )
        zones = tuple(
            TrendZone(start=start, end=end, colour=colour, opacity=opacity)
            for start, end, colour, opacity in compute_strategy_trend_zones(
                strategy, candles
            )
        )
        return StrategyOverlay(lines=lines, zones=zones)
