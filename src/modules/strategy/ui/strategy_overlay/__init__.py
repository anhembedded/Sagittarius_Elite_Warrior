"""`EPIC-022C` — turning a strategy into something a chart can draw.

@details Both modules replay a throwaway strategy instance over a list of
candles and return plot-ready data: named (x, y) series for indicator
lines, and merged (start, end, colour, opacity) spans for trend zones.
Nothing in either is Backtest-specific, and sharing them is what keeps the
live chart's lines identical to the backtest chart's for the same strategy
and parameters — two separate implementations would drift, and the user
would have no way to tell which one was lying.
"""

from .strategy_indicator_lines import (
    assign_strategy_line_colors,
    compute_strategy_indicator_lines,
)
from .strategy_trend_zones import compute_strategy_trend_zones

__all__ = [
    "assign_strategy_line_colors",
    "compute_strategy_indicator_lines",
    "compute_strategy_trend_zones",
]
