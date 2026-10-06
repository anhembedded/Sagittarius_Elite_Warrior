"""`ChartSeries` — the names of the data series a chart draws.

A strategy or an indicator says *which series* it draws (a long-trend EMA, the
RSI line); it never says what colour that is. The colour is the UI's decision,
made in one table (`support/charting/contracts/series_colours.py`), so a domain module
can import this vocabulary without importing a single colour.

A member's value is its own name, so two series that happen to share a colour
today (the MACD histogram and a neutral line) stay two members and can part
company without touching a caller.
"""

from __future__ import annotations

from enum import StrEnum, auto


class ChartSeries(StrEnum):
    """One data series, named for its meaning."""

    #: What closed up and what closed down: the candles, a profit, a loss.
    BULL = auto()
    BEAR = auto()

    #: The indicator scripts' own lines.
    EMA_20 = auto()
    EMA_50 = auto()
    EMA_100 = auto()
    EMA_200 = auto()
    RSI_14 = auto()
    MACD_LINE = auto()
    MACD_SIGNAL = auto()
    MACD_HISTOGRAM = auto()

    #: A line that flips with the trend, and the two that do not.
    TREND_UP_LINE = auto()
    TREND_DOWN_LINE = auto()
    NEUTRAL_LINE = auto()
    HIGHLIGHT_LINE = auto()

    #: The strategies' own lines.
    LONG_TREND_EMA = auto()
    ENTRY_EMA = auto()
    LONG_TERM_TREND_EMA = auto()

    #: What a strategy line gets when its strategy names no series for it.
    FALLBACK_GREEN = auto()
    FALLBACK_PURPLE = auto()
    FALLBACK_YELLOW = auto()
    FALLBACK_GREY = auto()
