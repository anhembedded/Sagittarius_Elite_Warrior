"""The drawdown underwater area chart (`BOT-106D`)."""

from __future__ import annotations

from pyqtgraph import (  # type: ignore[import-untyped]
    DateAxisItem,
    PlotCurveItem,
    PlotWidget,
    mkPen,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import BEAR_COLOR

#: Alpha (0-255) for the fill beneath the curve — visible as a tinted area
#: without drowning the axis grid behind it.
_FILL_ALPHA = 60


def _translucent(hex_color: str, alpha: int) -> QColor:
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color


class DrawdownChartWidget(QWidget):
    """One filled `PlotCurveItem` — `logic/performance_charts.py`'s
    `build_drawdown_chart_points()` already negates the drawdown percent, so
    the area draws below zero ("underwater") rather than above it.

    Deliberately its own small widget rather than reusing `ChartCard`
    (`support/charting/chart_card/`): that class is built for the
    candlestick/indicator/crosshair machinery of the main price chart, and
    none of it applies to one plain area curve.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel("No trade data yet")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        self._plot_widget = PlotWidget(
            axisItems={"bottom": DateAxisItem(orientation="bottom")}
        )
        self._plot_widget.setBackground("default")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.getPlotItem().getAxis("left").setLabel("Drawdown %")
        self._curve = PlotCurveItem(
            pen=mkPen(BEAR_COLOR, width=1),
            brush=_translucent(BEAR_COLOR, _FILL_ALPHA),
            fillLevel=0.0,
        )
        self._plot_widget.addItem(self._curve)
        self._plot_widget.setVisible(False)
        layout.addWidget(self._plot_widget, 1)

    def set_points(self, points: list[dict[str, float]]) -> None:
        has_points = bool(points)
        self._empty_label.setVisible(not has_points)
        self._plot_widget.setVisible(has_points)
        if not has_points:
            self._curve.setData([], [])
            return
        self._curve.setData(
            [point["t"] for point in points], [point["v"] for point in points]
        )
