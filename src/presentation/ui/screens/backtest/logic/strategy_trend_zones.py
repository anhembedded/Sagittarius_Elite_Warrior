from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import (
    TREND_ZONE_DOWN,
    TREND_ZONE_UP,
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

#: Matches BaseIndicatorScript.shade()'s own default opacity (BOT-032) —
#: a subtle tint, not a solid fill, so candles/lines drawn on top stay the
#: primary focus.
_ZONE_OPACITY = 0.15
_ZONE_COLORS = {
    TREND_ZONE_UP: BULL_COLOR,
    TREND_ZONE_DOWN: BEAR_COLOR,
}


def compute_strategy_trend_zones(
    strategy: BaseStrategy, klines: Iterable[MarketData]
) -> list[tuple[float, float, str, float]]:
    """
    @brief Replays `classify_trend_zone()` over `klines` (BOT-113), the same
    way `compute_strategy_indicator_lines()` replays `build_indicators()` —
    one full bar-by-bar pass over a fresh, throwaway strategy instance, so
    the drawn zones use the exact indicator readings `decide()` would have
    seen. Entirely separate from the real `StrategyEngine` run behind the
    actual `BacktestResult`.
    @details Consecutive bars classified into the same zone merge into one
    `(start_x, end_x, color, opacity)` span — `set_script_regions()`'s
    contract (BOT-032) draws one `LinearRegionItem` per span, so one span
    per bar would be needlessly many overlapping regions across a long
    trend run. A strategy that never overrides `classify_trend_zone()`
    (returns `None` for every bar) produces an empty list — no zones drawn,
    zero behavior change for every strategy predating BOT-113.
    """
    indicators = strategy.build_indicators()
    spans: list[tuple[float, float, str, float]] = []
    open_zone: str | None = None
    open_start = 0.0
    open_end = 0.0
    for candle in klines:
        values: dict[str, Any] = {}
        for name, indicator in indicators.items():
            value = indicator.update(candle.close_price)
            if value is not None:
                values[name] = value

        zone = None
        if len(values) == len(indicators):
            context = StrategyContext(candle=candle, indicators=values)
            zone = strategy.classify_trend_zone(context)

        timestamp = candle.close_time.timestamp()
        if zone is not None and zone == open_zone:
            open_end = timestamp
            continue

        if open_zone is not None:
            spans.append((open_start, open_end, _ZONE_COLORS[open_zone], _ZONE_OPACITY))
        if zone is not None:
            open_zone, open_start, open_end = zone, timestamp, timestamp
        else:
            open_zone = None

    if open_zone is not None:
        spans.append((open_start, open_end, _ZONE_COLORS[open_zone], _ZONE_OPACITY))
    return spans
