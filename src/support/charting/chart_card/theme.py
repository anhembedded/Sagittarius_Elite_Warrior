"""Shared colour constants for the chart_card package — the one table of what
a series colour *means*, so candlestick, volume, price-line and crosshair
rendering stay consistent.

Chart chrome (background, axes, crosshair, tags) is not here: it comes from the
widget's `QPalette` roles (`chart_chrome.py`), so the chart follows the
operating system's theme. What is here is colour that encodes data: a candle is
green because it closed up, a stop-loss line is the loss colour because it is
where a loss is taken. Each meaning is a name below, and a reader asks for the
meaning, never for a hex value.

BULL and BEAR are taken from `support/charting/contracts/series_colours.py`, the one
table of data series colours; every other meaning is either one of those two or
a named colour Qt and SVG both define, so no second literal table exists to
drift from it. The package imports nothing from the application's former `Palette`, which `EPIC-033M` deleted, and
nothing Qt-backed, so `StrategyChartOverlayService` can reach this file from the
application layer without paying for a Qt import
(`tests/unit/architecture/test_module_contribution_laziness.py`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.charting.contracts.chart_series import (
    ChartSeries,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.series_colours import (
    series_colour,
)

BULL_COLOR = series_colour(ChartSeries.BULL)
BEAR_COLOR = series_colour(ChartSeries.BEAR)
#: A series that means "neither up nor down": the out-of-sample divider, the
#: Monte Carlo paths. It was `CROSSHAIR_COLOR` until `EPIC-033G` moved the
#: crosshair, which is chrome, to `QPalette` roles (`chart_chrome.py`).
NEUTRAL_SERIES_COLOR = "gray"
#: BOT-111 — take-profit exit markers get their own color, distinct from the
#: plain bull/bear entry/exit scheme, so a broker-level TP fill reads
#: differently from a strategy-decided exit at a glance. The domain name is
#: kept even though the value is just a gold: what a reader needs here is
#: "this is the TP colour", not "this is gold".
TAKE_PROFIT_COLOR = "goldenrod"
#: `EPIC-029G` — what a bot's horizontal lines and bands mean, read at a
#: glance (`PriceLevelLayer`, `bots/ui/chart/overlay_items.py`). Each is a
#: series colour with a meaning, named for it, like the take-profit colour.
#: A price label's text: light on a dark fill, dark on a light one, chosen
#: per fill so the text never matches its own background (the PR 321
#: review: a light range-edge fill under light text read as a blank box).
PRICE_LEVEL_LABEL_COLOR = "white"
PRICE_LEVEL_LABEL_DARK_COLOR = "black"
EMPTY_LEVEL_COLOR = "gray"
PARTIAL_LEVEL_COLOR = "darkorange"
STOP_LOSS_COLOR = BEAR_COLOR
RANGE_EDGE_COLOR = "steelblue"
AVERAGE_COST_COLOR = "goldenrod"
SUGGESTION_BAND_COLOR = "gray"
INDICATOR_BAND_COLOR = "goldenrod"
