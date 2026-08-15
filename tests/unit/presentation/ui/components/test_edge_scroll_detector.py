"""
Tests for EdgeScrollDetector (BOT-035) — verifies it reports "near the left
edge" correctly without needing a real ChartCard/drag gesture: it only reacts
to plot.vb.sigRangeChangedManually, so pyqtgraph's own ViewBox is enough.
"""

import pyqtgraph as pg

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.edge_scroll_detector import (
    EdgeScrollDetector,
)

_INTERVAL = 60.0


def _history(count: int, start: float = 10_000.0) -> list[tuple[float, ...]]:
    return [(start + i * _INTERVAL, 1.0, 2.0, 0.5, 1.5) for i in range(count)]


def _plot_widget(qapp):
    widget = pg.PlotWidget()
    widget.show()
    return widget


def test_fires_when_panned_within_the_threshold_of_the_left_edge(qapp):
    plot = _plot_widget(qapp)
    history = _history(200)
    detector = EdgeScrollDetector(
        plot=plot.getPlotItem(), get_raw_history=lambda: history, edge_threshold_bars=20
    )
    fired = []
    detector.sig_near_left_edge.connect(lambda: fired.append(1))

    oldest = history[0][0]
    # 10 bars of empty space left before the true edge — well inside the
    # 20-bar threshold.
    x_min = oldest + 10 * _INTERVAL
    plot.getPlotItem().vb.setXRange(x_min, x_min + 200.0, padding=0)
    plot.getPlotItem().vb.sigRangeChangedManually.emit(
        plot.getPlotItem().vb.viewRange()
    )

    assert fired == [1]


def test_does_not_fire_when_far_from_the_left_edge(qapp):
    plot = _plot_widget(qapp)
    history = _history(200)
    detector = EdgeScrollDetector(
        plot=plot.getPlotItem(), get_raw_history=lambda: history, edge_threshold_bars=20
    )
    fired = []
    detector.sig_near_left_edge.connect(lambda: fired.append(1))

    oldest = history[0][0]
    # 100 bars of empty space left — well outside the 20-bar threshold.
    x_min = oldest + 100 * _INTERVAL
    plot.getPlotItem().vb.setXRange(x_min, x_min + 200.0, padding=0)
    plot.getPlotItem().vb.sigRangeChangedManually.emit(
        plot.getPlotItem().vb.viewRange()
    )

    assert fired == []


def test_is_a_safe_no_op_with_fewer_than_two_candles_loaded(qapp):
    plot = _plot_widget(qapp)
    detector = EdgeScrollDetector(
        plot=plot.getPlotItem(), get_raw_history=list, edge_threshold_bars=20
    )
    fired = []
    detector.sig_near_left_edge.connect(lambda: fired.append(1))

    plot.getPlotItem().vb.setXRange(0.0, 100.0, padding=0)
    plot.getPlotItem().vb.sigRangeChangedManually.emit(
        plot.getPlotItem().vb.viewRange()
    )

    assert fired == []
