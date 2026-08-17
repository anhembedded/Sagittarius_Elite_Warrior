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
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.candlestick_item import (
    FastCandlestickItem,
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
