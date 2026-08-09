"""
Tests for DevIndicatorScript (BOT-032) — the reference script other scripts
are copied from.

Its value is that every technique in it actually works, so these tests exist to
keep it honest: if the API changes under it, the showcase must fail here rather
than quietly become misleading documentation.
"""

import math

from Binace_Bot.src.domain.indicator_scripts import DevIndicatorScript

#: Enough bars for every declared indicator (slowest is MACD at ~35) to warm up,
#: with a wave so the EMAs actually cross rather than running parallel forever.
_CLOSES = [100.0 + 12.0 * math.sin(index / 6.0) for index in range(160)]


def _run_all(script, closes, make_candle):
    """Feeds a whole series, collecting every bar's lines and markers."""
    lines: list[dict] = []
    markers: list = []
    for index, close in enumerate(closes):
        lines.append(dict(script.compute(make_candle(close, index))))
        markers.extend(script.drain_markers())
    return lines, markers


def test_showcase_runs_a_full_history_without_raising(make_candle):
    """The whole point of a reference script: copying it must not blow up."""
    _run_all(DevIndicatorScript(), _CLOSES, make_candle)


def test_it_plots_its_three_permanent_lines_once_warm(make_candle):
    lines, _ = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    assert {"EMA 12", "EMA 26", "WMA 20"} <= set(lines[-1])


def test_nothing_is_plotted_before_anything_has_warmed_up(make_candle):
    assert DevIndicatorScript().compute(make_candle(100.0, 0)) == {}


def test_line_colour_changes_with_the_trend(make_candle):
    """Technique 6 — per-bar colour. A single fixed colour per line would make
    this impossible, so the data model has to carry colour per bar."""
    lines, _ = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    seen = {bar["EMA 12"].color for bar in lines if "EMA 12" in bar}
    assert len(seen) > 1, "EMA 12 never recoloured — the trend flip was lost"


def test_the_conditional_band_is_absent_on_some_bars(make_candle):
    """Technique 7 — `na`. plot(None) must skip the bar, not draw a gap-filling
    value, so the band appears only while the spread is widening."""
    lines, _ = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    warm = [bar for bar in lines if "EMA 26" in bar]
    with_band = [bar for bar in warm if "Widening band" in bar]
    assert 0 < len(with_band) < len(warm)


def test_it_marks_both_directions_of_the_ema_cross(make_candle):
    """Techniques 8 and 12 — cross detection driving a labelled marker."""
    _, markers = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    texts = {marker.text for marker in markers}
    assert {"Buy", "Sell"} <= texts


def test_buy_and_sell_markers_point_opposite_ways(make_candle):
    _, markers = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    directions = {marker.text: marker.direction for marker in markers}
    assert directions["Buy"] == "up"
    assert directions["Sell"] == "down"


def test_it_detects_an_indicator_crossing_price(make_candle):
    """Technique 9 — price is just another Series, needing no special API."""
    _, markers = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    assert any(marker.text == "WMA×Px" for marker in markers)


def test_it_detects_rsi_crossing_a_constant_level(make_candle):
    """Technique 10 — a level compared like any other line, and computed
    without being plotted (RSI's 0-100 scale would be meaningless over price)."""
    lines, markers = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    assert any(marker.text == "Overbought" for marker in markers)
    assert not any("RSI" in name for bar in lines for name in bar)


def test_it_reads_fields_off_a_compound_macd_reading(make_candle):
    """Technique 11 — MACD returns a MACDValue, not a float."""
    _, markers = _run_all(DevIndicatorScript(), _CLOSES, make_candle)

    assert any(marker.text == "Strong" for marker in markers)


def test_markers_are_drained_per_bar_not_accumulated(make_candle):
    """drain_markers() reports only the bar just computed — otherwise the
    presenter would redraw every past marker on every tick."""
    script = DevIndicatorScript()
    for index, close in enumerate(_CLOSES):
        script.compute(make_candle(close, index))
        script.drain_markers()

    script.compute(make_candle(_CLOSES[-1], len(_CLOSES)))
    assert len(script.drain_markers()) <= 2  # at most this bar's own marks


def test_every_plotted_line_has_a_recorded_colour(make_candle):
    """The presenter registers a curve using line_colors(), so a line that
    plotted a value but no colour would be undrawable."""
    script = DevIndicatorScript()
    lines, _ = _run_all(script, _CLOSES, make_candle)

    plotted = {name for bar in lines for name in bar}
    assert plotted <= set(script.line_colors())
