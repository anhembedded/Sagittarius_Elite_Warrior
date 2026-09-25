"""The overlaid simulated-equity-curve ("spaghetti") chart for `BOT-107B`'s
Monte Carlo dialog — same "own small `pyqtgraph` widget, not `ChartCard`"
precedent `_drawdown_chart_widget.py`/`_report_comparison_chart_widget.py`
already established, extended from 1-2 curves to a bounded sample of
simulated paths (`monte_carlo_simulation.py`'s own `DEFAULT_SAMPLE_CURVE_COUNT`)."""

from __future__ import annotations

from pyqtgraph import PlotCurveItem, PlotWidget, mkPen  # type: ignore[import-untyped]
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    CROSSHAIR_COLOR,
)

#: Low alpha so hundreds of overlaid paths read as a density cloud rather
#: than an opaque block — the same purpose `_drawdown_chart_widget.py`'s
#: `_translucent()` fill serves for one curve, needed here for many.
_LINE_ALPHA = 40


def _translucent_pen(hex_color: str, alpha: int) -> QPen:
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return mkPen(color, width=1)


class MonteCarloSpaghettiChartWidget(QWidget):
    """A bounded sample of simulated equity paths, all overlaid on one plain
    trade-index X axis (not `DateAxisItem`: a shuffled path's per-trade
    timestamps have no chronological meaning — `monte_carlo_rules.py`'s own
    `build_spaghetti_chart_series()` docstring). Curve count is unknown
    ahead of construction (bounded by the simulation's own sample size, not
    a fixed number), so curves are built lazily in `set_series()` rather
    than pre-allocated."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel("Run a simulation to see the equity paths")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        self._plot_widget = PlotWidget()
        self._plot_widget.setBackground("default")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.getPlotItem().getAxis("bottom").setLabel("Trade #")
        self._plot_widget.getPlotItem().getAxis("left").setLabel("Equity")
        self._plot_widget.setVisible(False)
        layout.addWidget(self._plot_widget, 1)
        self._curves: list[PlotCurveItem] = []

    def set_series(self, series: list[list[dict[str, float]]]) -> None:
        has_points = bool(series)
        self._empty_label.setVisible(not has_points)
        self._plot_widget.setVisible(has_points)
        for curve in self._curves:
            self._plot_widget.removeItem(curve)
        self._curves = []
        for points in series:
            curve = PlotCurveItem(
                x=[point["x"] for point in points],
                y=[point["y"] for point in points],
                pen=_translucent_pen(CROSSHAIR_COLOR, _LINE_ALPHA),
            )
            self._plot_widget.addItem(curve)
            self._curves.append(curve)
