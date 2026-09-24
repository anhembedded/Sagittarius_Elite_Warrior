"""The max-drawdown probability distribution chart for `BOT-107B`'s Monte
Carlo dialog — one bar per `monte_carlo_rules.build_drawdown_histogram_buckets()`
bucket. No histogram precedent existed anywhere in this codebase before this
(`volume_renderer.py`'s `BarGraphItem` renders candle volume bars, not a
statistical distribution) — this widget is that first use, same
`pg.BarGraphItem` API, own small `pyqtgraph` widget rather than `ChartCard`
for the same reason `_drawdown_chart_widget.py` gives."""

from __future__ import annotations

import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import BEAR_COLOR

from .logic.monte_carlo_rules import DrawdownHistogramBucket


class MonteCarloDrawdownHistogramWidget(QWidget):
    """One bar per bucket, centered on its range's midpoint, width matching
    the bucket's own range so adjacent bars touch with no gaps."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel("Run a simulation to see the drawdown distribution")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground("default")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.getPlotItem().getAxis("bottom").setLabel("Max Drawdown %")
        self._plot_widget.getPlotItem().getAxis("left").setLabel("Simulations")
        self._bars = pg.BarGraphItem(x=[], height=[], width=1.0, brush=BEAR_COLOR)
        self._plot_widget.addItem(self._bars)
        self._plot_widget.setVisible(False)
        layout.addWidget(self._plot_widget, 1)

    def set_buckets(self, buckets: list[DrawdownHistogramBucket]) -> None:
        has_buckets = bool(buckets)
        self._empty_label.setVisible(not has_buckets)
        self._plot_widget.setVisible(has_buckets)
        if not has_buckets:
            self._bars.setOpts(x=[], height=[], width=1.0)
            return
        widths = [bucket.range_end - bucket.range_start for bucket in buckets]
        # A single all-zero bucket (`build_drawdown_histogram_buckets()`'s
        # own "no drawdown at all" case) has `range_end == range_start`, so
        # its width would otherwise be 0 — a bar too thin to see.
        bar_width = max(max(widths), 1e-9)
        self._bars.setOpts(
            x=[
                (bucket.range_start + bucket.range_end) / 2
                if bucket.range_end > bucket.range_start
                else bucket.range_start
                for bucket in buckets
            ],
            height=[bucket.count for bucket in buckets],
            width=bar_width,
        )
