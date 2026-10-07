"""`EPIC-029D` — the grid's equity against buy-and-hold, on one time axis (D18).

An own small `pyqtgraph` plot, the precedent `backtesting/ui`'s comparison and
drawdown charts set, not a `ChartCard`: two lines need no candle machinery.
No legend (that pyqtgraph version's `LegendItem` has an initialisation-order
bug, as `_report_comparison_chart_widget.py` records); the labels under the
plot name the two lines in their colours' words.
"""

from __future__ import annotations

from collections.abc import Sequence

from pyqtgraph import (  # type: ignore[import-untyped]
    DateAxisItem,
    PlotCurveItem,
    PlotWidget,
    mkPen,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    EquityPoint,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BULL_COLOR,
    EMPTY_LEVEL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

KEY_TEXT = "Green: the grid's equity. Grey: buy and hold, from the same capital."


class EquityChart(QWidget):
    """@brief Two curves: the grid and buy-and-hold, value at each close."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plot = PlotWidget(axisItems={"bottom": DateAxisItem(orientation="bottom")})
        self.plot.setObjectName("plotGridBacktestEquity")
        self.plot.setBackground("default")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.getPlotItem().getAxis("left").setLabel("USDT")
        self.grid_curve = PlotCurveItem(pen=mkPen(BULL_COLOR, width=1))
        self.hold_curve = PlotCurveItem(pen=mkPen(EMPTY_LEVEL_COLOR, width=1))
        self.plot.addItem(self.hold_curve)
        self.plot.addItem(self.grid_curve)
        key = plain_label(KEY_TEXT)
        key.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot, 1)
        layout.addWidget(key)

    def show_equity(self, points: Sequence[EquityPoint]) -> None:
        times = [point.time.timestamp() for point in points]
        self.grid_curve.setData(times, [float(point.grid) for point in points])
        self.hold_curve.setData(times, [float(point.buy_and_hold) for point in points])

    def clear(self) -> None:
        self.grid_curve.setData([], [])
        self.hold_curve.setData([], [])
