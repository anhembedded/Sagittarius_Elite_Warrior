"""`EPIC-040D` — a bot's equity against buy-and-hold, on one time axis (D18), for any kind.

An own small `pyqtgraph` plot, the precedent `backtesting/ui`'s comparison and drawdown charts set, not
a `ChartCard`: two lines need no candle machinery. No legend (that pyqtgraph version's `LegendItem` has
an initialisation-order bug, as `_report_comparison_chart_widget.py` records); the labels under the
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    EquityPoint,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BULL_COLOR,
    EMPTY_LEVEL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

KEY_TEXT = "Green: the bot's equity. Grey: buy and hold, from the same capital."


class EquityPane(QWidget):
    """@brief Two curves: the bot and buy-and-hold, value at each close."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plot = PlotWidget(axisItems={"bottom": DateAxisItem(orientation="bottom")})
        self.plot.setObjectName("plotBacktestEquity")
        self.plot.setBackground("default")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.getPlotItem().getAxis("left").setLabel("USDT")
        self.bot_curve = PlotCurveItem(pen=mkPen(BULL_COLOR, width=1))
        self.benchmark_curve = PlotCurveItem(pen=mkPen(EMPTY_LEVEL_COLOR, width=1))
        self.plot.addItem(self.benchmark_curve)
        self.plot.addItem(self.bot_curve)
        key = plain_label(KEY_TEXT)
        key.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot, 1)
        layout.addWidget(key)

    def show_equity(self, points: Sequence[EquityPoint]) -> None:
        times = [point.time.timestamp() for point in points]
        self.bot_curve.setData(times, [float(point.bot) for point in points])
        self.benchmark_curve.setData(
            times, [float(point.benchmark) for point in points]
        )

    def point_count(self) -> int:
        """How many points the bot's curve holds (tests read it)."""
        return len(self.bot_curve.getData()[0])

    def clear(self) -> None:
        self.bot_curve.setData([], [])
        self.benchmark_curve.setData([], [])
