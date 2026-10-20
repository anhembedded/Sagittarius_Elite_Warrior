"""The one table of data series colours (`BOT-161`).

Every hex value that colours data on a chart is written here and nowhere else:
`tests/unit/architecture/test_stock_controls_only.py` names this file as its
single exemption from the colour-literal ban. A reader asks for a series by
name (`series_colour(ChartSeries.EMA_20)`); a strategy in a module's `domain/`
names the series it draws and never a colour (`contracts/chart_series.py`).

Every colour reads against the chart's background in both colour schemes
(`EPIC-043B`): at least 3:1 (WCAG 2.x 1.4.11, graphical objects) on a white base
and on the usual dark bases, `#1e1e1e` and `#202020`, checked by
`tests/unit/support/charting/test_series_colours_contrast.py`. One value serves
both schemes: these are read once, when a series is built, so a second table
keyed by scheme would never reach a line already drawn. Nine colours moved to the
nearest tone of the same hue that passes; the rest were already inside.

Chart chrome is not here: it follows the operating system's palette
(`chart_card/chart_chrome.py`). What is here encodes data — a candle is green
because it closed up, an EMA is red because it is the 20-bar one.

This file is Qt-free and sits outside `chart_card/`, whose package import pulls
in the toolkit: an indicator script and a strategy's application layer read it
without paying for Qt (`test_module_domain_is_qt_free.py`). `chart_card/
theme.py` holds the *meaning* names (take profit, stop loss, levels) and takes
bull and bear from here.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.charting.contracts.chart_series import (
    ChartSeries,
)

_SERIES_COLOURS: dict[ChartSeries, str] = {
    ChartSeries.BULL: "#25a296",
    ChartSeries.BEAR: "#ef5350",
    ChartSeries.EMA_20: "#e74c3c",
    ChartSeries.EMA_50: "#df7619",
    ChartSeries.EMA_100: "#00a1b5",
    ChartSeries.EMA_200: "#3498db",
    ChartSeries.RSI_14: "#984bb8",
    ChartSeries.MACD_LINE: "#2980b9",
    ChartSeries.MACD_SIGNAL: "#df7619",
    ChartSeries.MACD_HISTOGRAM: "#848E9C",
    ChartSeries.TREND_UP_LINE: "#0ca76a",
    ChartSeries.TREND_DOWN_LINE: "#F6465D",
    ChartSeries.NEUTRAL_LINE: "#848E9C",
    ChartSeries.HIGHLIGHT_LINE: "#bb880b",
    ChartSeries.LONG_TREND_EMA: "#f6465d",
    ChartSeries.ENTRY_EMA: "#2962ff",
    ChartSeries.LONG_TERM_TREND_EMA: "#9b59b6",
    ChartSeries.FALLBACK_GREEN: "#26a75c",
    ChartSeries.FALLBACK_PURPLE: "#9b59b6",
    ChartSeries.FALLBACK_YELLOW: "#ae8e0a",
    ChartSeries.FALLBACK_GREY: "#829596",
}

#: What a strategy's lines cycle through when it names no series for them. The
#: first four are the EMA ribbon's own, so a strategy whose indicators line up
#: with that script still looks familiar on the chart.
FALLBACK_LINE_SERIES: tuple[ChartSeries, ...] = (
    ChartSeries.EMA_20,
    ChartSeries.EMA_50,
    ChartSeries.EMA_100,
    ChartSeries.EMA_200,
    ChartSeries.FALLBACK_GREEN,
    ChartSeries.FALLBACK_PURPLE,
    ChartSeries.FALLBACK_YELLOW,
    ChartSeries.FALLBACK_GREY,
)


def series_colour(series: ChartSeries) -> str:
    """The colour a series is drawn in, as a hex string."""
    return _SERIES_COLOURS[series]
