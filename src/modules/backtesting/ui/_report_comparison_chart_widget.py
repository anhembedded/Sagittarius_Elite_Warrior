"""The overlaid equity-curve chart for `BOT-115D`'s report comparison
dialog — same "own small `pyqtgraph` widget, not `ChartCard`" precedent
`_drawdown_chart_widget.py` (`BOT-106D`) already established, extended to
two curves instead of one."""

from __future__ import annotations

from pyqtgraph import (  # type: ignore[import-untyped]
    DateAxisItem,
    PlotCurveItem,
    PlotWidget,
    mkPen,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BULL_COLOR,
    TAKE_PROFIT_COLOR,
)

#: Series A ("current result") vs series B (the loaded file) — reusing the
#: two colour constants `chart_card/theme.py` already exports rather than
#: importing `Palette` directly, which `test_app_styling_only_shrinks.py`
#: (ADR D21) tracks as a shrink-only ratchet: a new file importing it would
#: fail that guard even though this widget applies no stylesheet of its
#: own, only these two series pens.
_SERIES_A_COLOR = BULL_COLOR
_SERIES_B_COLOR = TAKE_PROFIT_COLOR


class ReportComparisonChartWidget(QWidget):
    """Two `PlotCurveItem`s, one per compared report, both plotted as
    "% of starting capital" (`logic/report_comparison_rules.py`'s
    `build_equity_comparison_series()` output) so runs with different
    `initial_balance` still overlay meaningfully."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel("Load a second report to compare equity curves")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        self._plot_widget = PlotWidget(
            axisItems={"bottom": DateAxisItem(orientation="bottom")}
        )
        self._plot_widget.setBackground("default")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.getPlotItem().getAxis("left").setLabel(
            "% of starting capital"
        )
        self._plot_widget.addLegend()
        self._curve_a = PlotCurveItem(pen=mkPen(_SERIES_A_COLOR, width=1), name="A")
        self._curve_b = PlotCurveItem(pen=mkPen(_SERIES_B_COLOR, width=1), name="B")
        self._plot_widget.addItem(self._curve_a)
        self._plot_widget.addItem(self._curve_b)
        self._plot_widget.setVisible(False)
        layout.addWidget(self._plot_widget, 1)

    def set_series(
        self, points_a: list[dict[str, float]], points_b: list[dict[str, float]]
    ) -> None:
        has_points = bool(points_a) or bool(points_b)
        self._empty_label.setVisible(not has_points)
        self._plot_widget.setVisible(has_points)
        self._curve_a.setData(
            [point["t"] for point in points_a], [point["v"] for point in points_a]
        )
        self._curve_b.setData(
            [point["t"] for point in points_b], [point["v"] for point in points_b]
        )
