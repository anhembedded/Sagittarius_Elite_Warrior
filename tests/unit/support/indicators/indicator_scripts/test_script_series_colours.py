"""`BOT-161`: each shipped script draws its lines in the colour it always did,
now read from the one series table (`support/charting/contracts/series_colours.py`)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts import (
    DevIndicatorScript,
    Ema20Script,
    Ema50Script,
    Ema100Script,
    Ema200Script,
    EmaCrossScript,
    EmaRibbonScript,
    MacdFullScript,
    Rsi14Script,
)

#: Long enough for EMA(200), the slowest line any script draws, to warm up.
_CLOSES = [100.0 + (index % 17) - 8 + index * 0.05 for index in range(260)]

_SINGLE_COLOUR_LINES = [
    (Ema20Script, {"EMA 20": "#e74c3c"}),
    (Ema50Script, {"EMA 50": "#e67e22"}),
    (Ema100Script, {"EMA 100": "#00bcd4"}),
    (Ema200Script, {"EMA 200": "#3498db"}),
    (
        EmaRibbonScript,
        {
            "EMA 20": "#e74c3c",
            "EMA 50": "#e67e22",
            "EMA 100": "#00bcd4",
            "EMA 200": "#3498db",
        },
    ),
    (Rsi14Script, {"RSI 14": "#8e44ad"}),
    (
        MacdFullScript,
        {"MACD": "#2980b9", "Signal": "#e67e22", "Histogram": "#848E9C"},
    ),
]


@pytest.mark.parametrize(("script_class", "expected"), _SINGLE_COLOUR_LINES)
def test_a_script_draws_each_line_in_its_own_colour(
    script_class, expected, run_script
) -> None:
    script = script_class()

    run_script(script, _CLOSES)

    assert dict(script.line_colors()) == expected


def test_the_trend_scripts_flip_between_the_up_and_down_colours(make_candle) -> None:
    for script_class in (EmaCrossScript, DevIndicatorScript):
        script = script_class()
        seen: set[str] = set()
        for index, close in enumerate(_CLOSES + _CLOSES[::-1]):
            script.compute(make_candle(close, index))
            seen.update(script.line_colors().values())

        assert {"#0ECB81", "#F6465D"} <= seen


def test_the_dev_script_draws_its_neutral_and_accent_lines_in_their_colours(
    make_candle,
) -> None:
    script = DevIndicatorScript()
    for index, close in enumerate(_CLOSES):
        script.compute(make_candle(close, index))

    colours = script.line_colors()

    assert colours["WMA 20"] == "#848E9C"
    assert colours["Widening band"] == "#F3BA2F"
