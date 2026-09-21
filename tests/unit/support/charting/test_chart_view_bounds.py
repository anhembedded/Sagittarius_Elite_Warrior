"""Regression tests: the chart must not be pannable into empty space.

Reported after a real dev-mode session in which the user dragged the Backtest
chart and ended up staring at a completely blank plot. The `[chart-range]`
diagnostics captured it exactly:

    x-range [...] | 0/5000 candles visible | data [1786772340.0, 1787072280.0]
    | view extends 1210361s BEFORE first candle and 0s AFTER last

`ChartCard.set_max_visible_x_range()` called `setLimits(maxXRange=...)`, which
caps how WIDE the view may get but places no bound on WHERE it may sit, so the
viewport could be dragged arbitrarily far from the data and legitimately show
nothing at all.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.support.charting.chart_card import (
    ChartCard,
)

_BAR_SECONDS = 60.0
_CANDLE_COUNT = 500


def _card_with_history(qapp) -> ChartCard:
    card = ChartCard("BTCUSDT")
    card.resize(1200, 700)
    card.show()
    base = 1_786_772_340.0
    card.render_historical_data(
        [
            (base + index * _BAR_SECONDS, 100.0 + (index % 7), 102.0, 98.0, 101.0)
            for index in range(_CANDLE_COUNT)
        ]
    )
    qapp.processEvents()
    return card


def _visible_candle_count(card: ChartCard) -> int:
    (min_x, max_x), _ = card.plot_layout.main_plot.vb.viewRange()
    return sum(1 for candle in card._raw_history if min_x <= candle[0] <= max_x)


def test_cannot_pan_far_past_the_oldest_candle_into_an_empty_view(qapp):
    card = _card_with_history(qapp)
    oldest = card._raw_history[0][0]

    # Ask for a view a fortnight earlier than any data that exists -- the same
    # shape of range the user's log recorded (~1.2M seconds before the first
    # candle).
    card.plot_layout.main_plot.setXRange(
        oldest - 1_200_000.0, oldest - 1_200_000.0 + 9_300.0, padding=0
    )
    qapp.processEvents()

    assert _visible_candle_count(card) > 0, (
        "the view was allowed to move entirely off the loaded data, leaving a "
        "blank chart with no candles drawn"
    )
    card.cleanup()


def test_cannot_pan_far_past_the_newest_candle_into_an_empty_view(qapp):
    card = _card_with_history(qapp)
    newest = card._raw_history[-1][0]

    card.plot_layout.main_plot.setXRange(
        newest + 1_200_000.0, newest + 1_200_000.0 + 9_300.0, padding=0
    )
    qapp.processEvents()

    assert _visible_candle_count(card) > 0, (
        "the view was allowed to move past the newest candle into empty future "
        "time, leaving a blank chart"
    )
    card.cleanup()


def test_a_reasonable_margin_past_the_newest_candle_is_still_allowed(qapp):
    """Clamping must not glue the last candle to the right edge.

    Traders expect a little breathing room ahead of the most recent bar; a
    clamp that forbids it would be a usability regression, so the bound is a
    margin past the data rather than the data's exact extent.
    """
    card = _card_with_history(qapp)
    newest = card._raw_history[-1][0]

    card.plot_layout.main_plot.setXRange(
        newest - 20 * _BAR_SECONDS, newest + 5 * _BAR_SECONDS, padding=0
    )
    qapp.processEvents()

    (_, max_x), _ = card.plot_layout.main_plot.vb.viewRange()
    assert max_x > newest, (
        "the clamp is too tight: it should still be possible to show empty "
        "space just ahead of the newest candle"
    )
    card.cleanup()


def test_subplots_have_identical_x_limits_to_main_plot(qapp):
    """BUG-132: Subplots (volume, indicators) must share the exact same X limits
    as the main plot so they cannot zoom in/out independently or diverge.
    """
    card = _card_with_history(qapp)
    card.add_subplot_indicator("RSI", "#ff00ff")
    qapp.processEvents()

    main_limits = card.plot_layout.main_plot.vb.state["limits"]
    for sub_plot in card.plot_layout.sub_plots:
        sub_limits = sub_plot.vb.state["limits"]
        assert sub_limits["xLimits"] == main_limits["xLimits"], (
            f"subplot xLimits {sub_limits['xLimits']} do not match main {main_limits['xLimits']}"
        )
        assert sub_limits["xRange"] == main_limits["xRange"], (
            f"subplot xRange {sub_limits['xRange']} does not match main {main_limits['xRange']}"
        )
    card.cleanup()


def test_chart_has_minimum_zoom_in_limit(qapp):
    """BUG-132: The chart must have a minXRange preventing zoom in to empty space/glitch."""
    card = _card_with_history(qapp)
    min_x_range = card.plot_layout.main_plot.vb.state["limits"]["xRange"][0]
    assert min_x_range is not None and min_x_range > 0, (
        "chart has no minimum zoom-in limit (minXRange)"
    )
    card.cleanup()


def test_volume_subplot_zoom_stays_synchronized_with_main_plot(qapp):
    """BUG-132: Zooming on volume subplot must not zoom wider or narrower than main_plot."""
    card = _card_with_history(qapp)
    volume_vb = card._volume_plot.vb

    # Try zooming OUT on volume plot
    volume_vb.scaleBy(x=10.0)
    qapp.processEvents()

    (main_min, main_max), _ = card.plot_layout.main_plot.vb.viewRange()
    (vol_min, vol_max), _ = volume_vb.viewRange()
    main_w = main_max - main_min
    vol_w = vol_max - vol_min

    assert abs(main_w - vol_w) < 1e-3, (
        f"volume zoomed wider than main plot: vol={vol_w} vs main={main_w}"
    )

    # Try zooming IN on volume plot to extreme level
    volume_vb.scaleBy(x=0.00001)
    qapp.processEvents()

    (main_min, main_max), _ = card.plot_layout.main_plot.vb.viewRange()
    (vol_min, vol_max), _ = volume_vb.viewRange()
    main_w = main_max - main_min
    vol_w = vol_max - vol_min

    assert abs(main_w - vol_w) < 1e-3, (
        f"volume zoomed narrower than main plot: vol={vol_w} vs main={main_w}"
    )
    assert vol_w >= _BAR_SECONDS * 2, f"volume zoomed in beyond minimum candle bounds: {vol_w}"
    card.cleanup()

