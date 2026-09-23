"""`PROP-003` — `MarkerLayer`'s zoom-adaptive PnL/reason badge.

A badge is a persistent, always-visible label next to a marker's triangle
(as opposed to the tooltip, which already showed the same information on
hover) — shown only once the viewport is zoomed in enough
(`MarkerDensityMode.DETAILED`) that there is room for it, per the
proposal's own §3.1 thresholds (`test_marker_lod.py` proves those
thresholds themselves; this file proves `MarkerLayer` actually applies
them to real scene items).
"""

import pyqtgraph as pg
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.marker_layer import (
    MarkerLayer,
)

_KEY = "backtest_trades"


def _marker(x: float, text: str = "CLOSE LONG") -> tuple:
    return (x, 100.0, text, "#0ECB81", "down")


def test_badge_is_hidden_when_bar_seconds_was_never_set(qapp):
    # No `set_bar_seconds()` call at all — must behave exactly as before
    # `PROP-003` (DENSE, no badges), never guess a candle count.
    layer = MarkerLayer(pg.PlotItem())
    markers = [_marker(0.0)]

    layer.set_markers(_KEY, markers, badges=["+2.10%"])

    item = layer._active_items[_KEY][0]
    assert item._badge_item.isVisible() is False


def test_badge_is_hidden_in_dense_mode(qapp):
    layer = MarkerLayer(pg.PlotItem())
    layer.set_bar_seconds(60.0)
    markers = [_marker(0.0)]
    layer.set_markers(_KEY, markers, badges=["+2.10%"])

    # 100 candles visible at 60s spacing over a 6000s window -> DENSE.
    layer.refresh_window(0.0, 6000.0)

    item = layer._active_items[_KEY][0]
    assert item._badge_item.isVisible() is False


def test_badge_is_hidden_in_medium_mode(qapp):
    layer = MarkerLayer(pg.PlotItem())
    layer.set_bar_seconds(60.0)
    markers = [_marker(0.0)]
    layer.set_markers(_KEY, markers, badges=["+2.10%"])

    # 50 candles visible -> MEDIUM (30-80 band).
    layer.refresh_window(0.0, 50.0 * 60.0)

    item = layer._active_items[_KEY][0]
    assert item._badge_item.isVisible() is False


def test_badge_appears_in_detailed_mode_with_its_own_text(qapp):
    layer = MarkerLayer(pg.PlotItem())
    layer.set_bar_seconds(60.0)
    markers = [_marker(0.0)]
    layer.set_markers(_KEY, markers, badges=["+2.10%"])

    # 10 candles visible -> DETAILED (< 30).
    layer.refresh_window(0.0, 10.0 * 60.0)

    item = layer._active_items[_KEY][0]
    assert item._badge_item.isVisible() is True
    assert item._badge_item.text() == "+2.10%"


def test_a_marker_with_no_badge_never_shows_one_even_when_detailed(qapp):
    layer = MarkerLayer(pg.PlotItem())
    layer.set_bar_seconds(60.0)
    markers = [_marker(0.0)]
    layer.set_markers(_KEY, markers, badges=[None])

    layer.refresh_window(0.0, 10.0 * 60.0)

    item = layer._active_items[_KEY][0]
    assert item._badge_item.isVisible() is False


def test_crossing_a_density_threshold_updates_the_badge_without_changing_markers(qapp):
    """A pan that doesn't change which markers are visible must still
    re-evaluate the badge once the density band itself changes — the
    early-return in `_materialize_visible_slice()` compares display
    markers, not the density mode, so this mutation would go undetected
    without also tracking the mode."""
    layer = MarkerLayer(pg.PlotItem())
    layer.set_bar_seconds(60.0)
    markers = [_marker(0.0)]
    layer.set_markers(_KEY, markers, badges=["+2.10%"])
    layer.refresh_window(0.0, 6000.0)  # DENSE
    item_before = layer._active_items[_KEY][0]
    assert item_before._badge_item.isVisible() is False

    layer.refresh_window(0.0, 10.0 * 60.0)  # DETAILED, same single marker

    item_after = layer._active_items[_KEY][0]
    assert item_after._badge_item.isVisible() is True


def test_an_aggregated_marker_never_shows_a_badge(qapp):
    """A dense cluster of trades collapsed into one aggregate item must not
    show any single trade's badge — that would misrepresent the group."""
    layer = MarkerLayer(pg.PlotItem())
    layer.set_bar_seconds(0.01)  # tiny spacing -> huge visible-candle count
    markers = [_marker(float(i)) for i in range(50)]
    badges = ["+1.00%"] * 50
    layer.set_markers(_KEY, markers, badges=badges)

    # A fallback 1200px viewport (no real window here) caps full labels at
    # 10; 50 identical-identity markers must aggregate. At this
    # bar_seconds, the density mode is DETAILED regardless.
    layer.refresh_window(0.0, 49.0)

    assert layer.active_marker_count(_KEY) < 50
    active_items = layer._active_items[_KEY]
    assert active_items
    assert all(item._badge_item.isVisible() is False for item in active_items.values())
