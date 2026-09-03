"""Tests for FastCandlestickItem's viewport-change invalidation (BOT-072).

BUG-002: after zooming out far then back in, candles vanish across most of
the X axis. Root cause (see Tasks/backlog/BOT-072_chart_stale_viewport_
window_on_zoom.md): paint() reads the ViewBox's live viewRange() via
_visible_history_slice(), but the item never overrides viewRangeChanged()
(pyqtgraph's GraphicsItem hook, connected automatically once the item is
added to a real ViewBox) — so nothing calls self.update() when the
viewport changes, and Qt can skip repainting a region it doesn't think
changed, leaving a stale slice on screen.
"""

import pyqtgraph as pg
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    volume_renderer,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.candlestick_item import (
    FastCandlestickItem,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.viewport_windowing import (
    DEFAULT_VISIBLE_PADDING_WIDTHS,
)


class _SpyCandlestickItem(FastCandlestickItem):
    """Counts calls to update() without touching Qt's own dispatch."""

    def __init__(self, data=None):
        self.update_call_count = 0
        super().__init__(data)

    def update(self, *args, **kwargs):
        self.update_call_count += 1
        super().update(*args, **kwargs)


def _make_candles(count: int) -> list[tuple[float, float, float, float, float]]:
    return [(float(i * 60), 100.0, 101.0, 99.0, 100.0) for i in range(count)]


def test_viewport_range_change_invalidates_the_item_for_repaint(qapp):
    plot_item = pg.PlotItem()
    candles = _make_candles(200)
    item = _SpyCandlestickItem(candles)
    plot_item.addItem(item)
    plot_item.vb.setRange(xRange=(candles[0][0], candles[-1][0]), padding=0)
    item.update_call_count = 0  # ignore whatever setup triggered

    plot_item.vb.setRange(xRange=(candles[50][0], candles[100][0]), padding=0)

    assert item.update_call_count > 0


def test_visible_history_slice_reflects_the_current_viewport_after_a_range_change(
    qapp,
):
    plot_item = pg.PlotItem()
    candles = _make_candles(200)
    item = FastCandlestickItem(candles)
    plot_item.addItem(item)
    plot_item.vb.setRange(xRange=(candles[0][0], candles[-1][0]), padding=0)

    plot_item.vb.setRange(xRange=(candles[50][0], candles[100][0]), padding=0)

    visible = item._visible_history_slice()
    assert visible[0][0] >= candles[40][0]
    assert visible[-1][0] <= candles[110][0]


def test_data_bounds_stays_windowed_when_orthorange_falls_between_two_candles(qapp):
    """Real user report: after zooming in far enough, the candle Y-axis
    froze while the volume subplot kept adjusting. Root cause: at that
    zoom level the ViewBox's `orthoRange` window (candles are 60 apart
    here) can fall entirely between two candle timestamps — the un-padded
    `visible_slice_indices` lookup `dataBounds(ax=1, orthoRange=...)` used
    then returns an empty slice, which fell through to the full-history
    bounds fallback below. Once that happened, every further zoom-in was
    an even narrower (still-empty) window, so the Y range stayed frozen at
    the full history's bounds forever — confirmed by direct measurement
    (see BUG report), not assumed. `candle_width` here is `60 / 3 = 20`,
    so the padded window (`candle_width * _VISIBLE_PADDING_WIDTHS = 40`)
    still brackets the nearest candle even though the requested
    `orthoRange` (20 wide) does not contain any candle's exact timestamp."""
    candles = [(float(i * 60), 100.0, 101.0, 99.0, 100.0) for i in range(200)]
    # An obviously different range from the local candles around index 100,
    # so a wrong fallback to the full-history bounds is unmistakable.
    candles[0] = (candles[0][0], 100.0, 500.0, -500.0, 100.0)
    item = FastCandlestickItem(candles)

    t = candles[100][0]
    min_y, max_y = item.dataBounds(1, orthoRange=(t + 10, t + 30))

    assert (min_y, max_y) == (99.0, 101.0)


def test_candlestick_and_volume_share_one_visible_padding_constant(qapp):
    """Drift guard: `FastCandlestickItem` and `VolumeItem` used to each
    declare their own `_VISIBLE_PADDING_WIDTHS = 2.0` — `volume_renderer.
    py`'s own comment literally said "mirrors FastCandlestickItem.
    _VISIBLE_PADDING_WIDTHS" rather than importing it. That drift is
    exactly the shape of bug this file's other new test regresses (one
    renderer's padding usage fell out of sync with the other's). Both now
    derive from one shared constant — this only catches a *value* drift
    (someone re-introducing a literal instead of importing), not a
    *usage* drift (a call site forgetting to apply it, which the other
    test covers), but it removes the easy way to reintroduce the former."""
    assert FastCandlestickItem._VISIBLE_PADDING_WIDTHS == DEFAULT_VISIBLE_PADDING_WIDTHS
    assert volume_renderer._VISIBLE_PADDING_WIDTHS == DEFAULT_VISIBLE_PADDING_WIDTHS
