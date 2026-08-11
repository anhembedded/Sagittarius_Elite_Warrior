"""
Tests for the two reference scripts (BOT-032 Phase 1).

Values are cross-checked against feeding the same closes straight into the
existing EMA/MACD classes — proving a script only composes them and never
reimplements the maths.
"""

from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
    EmaRibbonScript,
    MacdFullScript,
)
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.macd import MACD

#: Long enough for EMA(200) — the ribbon's slowest line — to warm up.
_CLOSES = [100.0 + (index % 17) - 8 for index in range(260)]


# ---------------------------------------------------------------------------
# EMA Ribbon
# ---------------------------------------------------------------------------


def test_ema_ribbon_plots_all_four_lines_as_an_overlay(run_script):
    result = run_script(EmaRibbonScript(), _CLOSES)

    assert set(result) == {"EMA 20", "EMA 50", "EMA 100", "EMA 200"}
    assert EmaRibbonScript.overlay is True


def test_ema_ribbon_values_match_standalone_ema_instances(run_script):
    result = run_script(EmaRibbonScript(), _CLOSES)

    for period, line in ((20, "EMA 20"), (50, "EMA 50"), (200, "EMA 200")):
        reference = EMA(period)
        expected = None
        for close in _CLOSES:
            expected = reference.update(close)
        assert result[line].value == expected


def test_ema_ribbon_slow_lines_stay_absent_until_warmed_up(run_script):
    """EMA(200) needs 200 bars — a short history must yield only the fast lines
    rather than a fabricated value."""
    result = run_script(EmaRibbonScript(), _CLOSES[:60])

    assert set(result) == {"EMA 20", "EMA 50"}


def test_ema_ribbon_lines_have_distinct_colors(run_script):
    script = EmaRibbonScript()
    run_script(script, _CLOSES[:30])

    colors = script.line_colors()
    assert len(set(colors.values())) == len(colors)


# ---------------------------------------------------------------------------
# MACD (full)
# ---------------------------------------------------------------------------


def test_macd_full_plots_all_three_components_on_a_subplot(run_script):
    """The point of this script: it keeps signal/histogram, which the Dev
    Board's built-in MACD checkbox throws away."""
    result = run_script(MacdFullScript(), _CLOSES)

    assert set(result) == {"MACD", "Signal", "Histogram"}
    assert MacdFullScript.overlay is False


def test_macd_full_values_match_a_standalone_macd_instance(run_script):
    result = run_script(MacdFullScript(), _CLOSES)

    reference = MACD()
    expected = None
    for close in _CLOSES:
        expected = reference.update(close)

    assert result["MACD"].value == expected.macd
    assert result["Signal"].value == expected.signal
    assert result["Histogram"].value == expected.histogram


def test_macd_full_plots_nothing_while_warming_up(run_script):
    assert run_script(MacdFullScript(), _CLOSES[:5]) == {}
