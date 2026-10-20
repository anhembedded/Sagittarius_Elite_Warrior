"""The overlaid equity-curve chart for `BOT-115D`'s report comparison
dialog — same "own small `pyqtgraph` widget, not `ChartCard`" precedent
`_drawdown_chart_widget.py` (`BOT-106D`) already established, extended to
two curves instead of one."""

from __future__ import annotations

from pyqtgraph import (  # type: ignore[import-untyped]
    PlotCurveItem,
    PlotWidget,
    mkPen,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BULL_COLOR,
    TAKE_PROFIT_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.zoned_date_axis import (
    ZonedDateAxisItem,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
)

#: Series A ("current result") vs series B (the loaded file) — reusing the
#: two colour constants `chart_card/theme.py` already exports, the one place
#: that names what a chart series means; this widget applies no stylesheet of
#: its own, only these two series pens.
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

        self._empty_label = plain_label("Load a second report to compare equity curves")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        self._plot_widget = PlotWidget(
            axisItems={"bottom": ZonedDateAxisItem(DEFAULT_TIMEZONE)}
        )
        self._plot_widget.setBackground("default")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.getPlotItem().getAxis("left").setLabel(
            "% of starting capital"
        )
        # No `addLegend()`: this pyqtgraph version's `LegendItem`/`LabelItem`
        # has a real initialization-order bug (`LabelItem.sizeHint()` reads
        # `self._sizeHint` before `__init__` sets it) that a resize pass
        # during dialog construction can trigger on a cold process —
        # reproduced deterministically running this widget's own dialog
        # test in isolation. `_drawdown_chart_widget.py` never calls
        # `addLegend()` for the same reason; the dialog's own "Column A"/
        # "Column B" labels above the chart already say which series is
        # which, so a legend duplicates that rather than adding information.
        self._curve_a = PlotCurveItem(pen=mkPen(_SERIES_A_COLOR, width=1))
        self._curve_b = PlotCurveItem(pen=mkPen(_SERIES_B_COLOR, width=1))
        self._plot_widget.addItem(self._curve_a)
        self._plot_widget.addItem(self._curve_b)
        self._plot_widget.setVisible(False)
        layout.addWidget(self._plot_widget, 1)

    def set_display_timezone(self, zone: str) -> None:
        """The time axis reads in `zone` (`BUG-243`)."""
        axis = self._plot_widget.getPlotItem().getAxis("bottom")
        if isinstance(axis, ZonedDateAxisItem):
            axis.set_display_zone(zone)

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
