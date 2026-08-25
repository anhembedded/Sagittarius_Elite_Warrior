from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy

#: First 4 entries match ema_ribbon_script.py's own EMA 20/50/100/200 colors
#: (red/orange/cyan/blue) so a strategy whose indicators happen to line up
#: 1:1 with that script still looks familiar on this chart; the rest are
#: fallbacks for strategies with more lines than that.
_LINE_COLOR_PALETTE = (
    "#e74c3c",  # token-exempt: indicator series colour, not chrome
    "#e67e22",  # token-exempt: indicator series colour, not chrome
    "#00bcd4",  # token-exempt: indicator series colour, not chrome
    "#3498db",  # token-exempt: indicator series colour, not chrome
    "#2ecc71",  # token-exempt: indicator series colour, not chrome
    "#9b59b6",  # token-exempt: indicator series colour, not chrome
    "#f1c40f",  # token-exempt: indicator series colour, not chrome
    "#95a5a6",  # token-exempt: indicator series colour, not chrome
)


def compute_strategy_indicator_lines(
    strategy: BaseStrategy, klines: Iterable[MarketData]
) -> dict[str, tuple[list[float], list[float]]]:
    """
    @brief Replays `strategy.build_indicators()` over `klines` to reconstruct
    the exact indicator series `StrategyEngine` would have fed `decide()`
    with (BOT-046 gives every strategy this same, real `build_indicators()`
    — no more guessing/using an unrelated indicator script for the chart).
    @details A fresh feed, entirely separate from the real `StrategyEngine`
    run behind the `BacktestResult` — this only computes points to draw, it
    never touches `strategy_engine.py`. Bars still warming up (`update()`
    returns `None`) are skipped, same as any indicator's normal behavior.
    """
    indicators = strategy.build_indicators()
    lines: dict[str, tuple[list[float], list[float]]] = {}
    for candle in klines:
        timestamp = candle.close_time.timestamp()
        for name, indicator in indicators.items():
            value = indicator.update(candle.close_price)
            if value is None:
                continue
            for line_name, scalar in _flatten(name, value):
                x_data, y_data = lines.setdefault(line_name, ([], []))
                x_data.append(timestamp)
                y_data.append(scalar)
    return lines


def _flatten(name: str, value: Any) -> list[tuple[str, float]]:
    """A scalar reading (e.g. `EMA`) draws as one line named after its
    indicator key; a multi-field reading (e.g. `MACD`'s `MACDValue`) draws
    one line per field, named `f"{key}_{field}"` — nothing here needs to
    know the field names ahead of time."""
    if dataclasses.is_dataclass(value):
        return [
            (f"{name}_{f.name}", getattr(value, f.name))
            for f in dataclasses.fields(value)
        ]
    return [(name, value)]


def assign_strategy_line_colors(
    line_names: Sequence[str], overrides: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Deterministic color per line, in the order the caller lists them —
    cycles through `_LINE_COLOR_PALETTE` if a strategy has more lines than
    it has colors. `overrides` (BOT-111, from `BaseStrategy.chart_line_colors()`)
    takes priority for any name it names; every other line still gets the
    next palette color in order, so a strategy overriding some but not all
    of its lines doesn't skip palette slots for the ones it left alone."""
    overrides = overrides or {}
    colors: dict[str, str] = {}
    palette_index = 0
    for name in line_names:
        if name in overrides:
            colors[name] = overrides[name]
            continue
        colors[name] = _LINE_COLOR_PALETTE[palette_index % len(_LINE_COLOR_PALETTE)]
        palette_index += 1
    return colors
