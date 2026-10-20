"""`BOT-161`: every data series colour is read from one table, and each one is
the colour the chart showed before the table existed.

The expected hex values are written out here on purpose — they are what the
screen showed on 2026-10-06, so a table entry that drifts fails against a
value the table did not supply.

Nine values moved on 2026-10-20 (`EPIC-043B`, the owner's `PRO-009`), because they
failed 3:1 against a light or a dark chart background; `_MOVED_BY_EPIC_043B` names
each from-and-to, and `test_series_colours_contrast.py` holds the reason.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.chart_series import (
    ChartSeries,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.series_colours import (
    FALLBACK_LINE_SERIES,
    series_colour,
)

_BEFORE_BOT_161 = {
    ChartSeries.BULL: "#26a69a",
    ChartSeries.BEAR: "#ef5350",
    ChartSeries.EMA_20: "#e74c3c",
    ChartSeries.EMA_50: "#e67e22",
    ChartSeries.EMA_100: "#00bcd4",
    ChartSeries.EMA_200: "#3498db",
    ChartSeries.RSI_14: "#8e44ad",
    ChartSeries.MACD_LINE: "#2980b9",
    ChartSeries.MACD_SIGNAL: "#e67e22",
    ChartSeries.MACD_HISTOGRAM: "#848E9C",
    ChartSeries.TREND_UP_LINE: "#0ECB81",
    ChartSeries.TREND_DOWN_LINE: "#F6465D",
    ChartSeries.NEUTRAL_LINE: "#848E9C",
    ChartSeries.HIGHLIGHT_LINE: "#F3BA2F",
    ChartSeries.LONG_TREND_EMA: "#f6465d",
    ChartSeries.ENTRY_EMA: "#2962ff",
    ChartSeries.LONG_TERM_TREND_EMA: "#9b59b6",
    ChartSeries.FALLBACK_GREEN: "#2ecc71",
    ChartSeries.FALLBACK_PURPLE: "#9b59b6",
    ChartSeries.FALLBACK_YELLOW: "#f1c40f",
    ChartSeries.FALLBACK_GREY: "#95a5a6",
}


#: What each moved colour became (`EPIC-043B`); the same hue, the nearest tone that reads on
#: both a white and a dark chart.
_MOVED_BY_EPIC_043B = {
    "#26a69a": "#25a296",
    "#e67e22": "#df7619",
    "#00bcd4": "#00a1b5",
    "#8e44ad": "#984bb8",
    "#0ecb81": "#0ca76a",
    "#f3ba2f": "#bb880b",
    "#2ecc71": "#26a75c",
    "#f1c40f": "#ae8e0a",
    "#95a5a6": "#829596",
}


def _expected(hex_value: str) -> str:
    return _MOVED_BY_EPIC_043B.get(hex_value.lower(), hex_value)


@pytest.mark.parametrize(("series", "hex_value"), _BEFORE_BOT_161.items())
def test_a_series_keeps_the_colour_it_had_before_the_table_unless_epic_043b_moved_it(
    series: ChartSeries, hex_value: str
) -> None:
    assert series_colour(series) == _expected(hex_value)


def test_every_series_has_a_colour_and_the_test_knows_it() -> None:
    assert set(_BEFORE_BOT_161) == set(ChartSeries)


def test_the_themes_bull_and_bear_are_the_tables() -> None:
    assert (BULL_COLOR, BEAR_COLOR) == ("#25a296", "#ef5350")
    assert series_colour(ChartSeries.BULL) == BULL_COLOR
    assert series_colour(ChartSeries.BEAR) == BEAR_COLOR


def test_the_fallback_line_palette_is_the_one_a_strategy_chart_always_had() -> None:
    assert [series_colour(series) for series in FALLBACK_LINE_SERIES] == [
        "#e74c3c",
        "#df7619",
        "#00a1b5",
        "#3498db",
        "#26a75c",
        "#9b59b6",
        "#ae8e0a",
        "#829596",
    ]
