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

#: BUG-078 — a ranging market oscillating around the trend EMA flips
#: `classify_trend_zone()` on nearly every bar. Without a floor, each 1-bar
#: (sometimes zero-width) flip still became its own `LinearRegionItem`, and
#: a run of alternating red/green 1-bar-wide regions renders as a dense,
#: near-opaque striped band that hides the candles under it — the opposite
#: of the "subtle tint" `_ZONE_OPACITY` intends, and meaningless besides:
#: one bar isn't a "long-term trend". Below this many consecutive bars, a
#: zone is dropped rather than drawn.
_MIN_ZONE_BARS = 3


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
    zero behavior change for every strategy predating BOT-113. A run
    shorter than `_MIN_ZONE_BARS` bars is dropped entirely (BUG-078) rather
    than drawn — see that constant's own comment.
    """
    indicators = strategy.build_indicators()
    spans: list[tuple[float, float, str, float]] = []
    open_zone: str | None = None
    open_start = 0.0
    open_end = 0.0
    open_bar_count = 0
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
            open_bar_count += 1
            continue

        if open_zone is not None and open_bar_count >= _MIN_ZONE_BARS:
            spans.append((open_start, open_end, _ZONE_COLORS[open_zone], _ZONE_OPACITY))
        if zone is not None:
            open_zone, open_start, open_end, open_bar_count = (
                zone,
                timestamp,
                timestamp,
                1,
            )
        else:
            open_zone = None
            open_bar_count = 0

    if open_zone is not None and open_bar_count >= _MIN_ZONE_BARS:
        spans.append((open_start, open_end, _ZONE_COLORS[open_zone], _ZONE_OPACITY))
    return spans
