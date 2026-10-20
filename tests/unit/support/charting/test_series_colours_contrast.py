"""`EPIC-043B` — every data series colour reads against the chart's background in both schemes.

A line or a candle is a graphical object, so WCAG 2.x 1.4.11 asks 3:1 against what it is drawn
on. The chart's background is the palette's `Base` (`chart_chrome.py`): white in the light
scheme, and in the dark one the usual `#1e1e1e` (Fusion and VS Code) or `#202020` (Windows 11).
The platform draws the real dark palette on the person's machine (Qt's offscreen platform
cannot, `EPIC-043A`), so these are the bases the check stands on.

Before this check nine of the 21 colours failed on white and one (the RSI purple) on dark.

Retire when: the series colours are drawn from the platform's own accent palette.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.charting.contracts.chart_series import (
    ChartSeries,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.series_colours import (
    series_colour,
)

MIN_GRAPHIC_CONTRAST = 3.0

_BASES = {
    "light": "#ffffff",
    "dark (Fusion, VS Code)": "#1e1e1e",
    "dark (Windows 11)": "#202020",
}


def _channel(value: int) -> float:
    unit = value / 255
    return unit / 12.92 if unit <= 0.03928 else ((unit + 0.055) / 1.055) ** 2.4


def _luminance(hex_value: str) -> float:
    digits = hex_value.lstrip("#")
    red, green, blue = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("base", _BASES.values(), ids=_BASES.keys())
@pytest.mark.parametrize("series", list(ChartSeries), ids=lambda s: s.name)
def test_a_series_colour_reads_on_each_chart_background(
    series: ChartSeries, base: str
) -> None:
    assert contrast(series_colour(series), base) >= MIN_GRAPHIC_CONTRAST


def test_the_check_fails_a_colour_that_does_not_read() -> None:
    """The check is not vacuous: the old yellow on white is 1.7:1, the old purple on dark 2.8:1."""
    assert contrast("#f1c40f", "#ffffff") < MIN_GRAPHIC_CONTRAST
    assert contrast("#8e44ad", "#1e1e1e") < MIN_GRAPHIC_CONTRAST
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
