"""`EPIC-040D` — a bot's equity against buy-and-hold, on one time axis (D18), for any kind.

An own small `pyqtgraph` plot, the precedent `backtesting/ui`'s comparison and drawdown charts set, not
a `ChartCard`: two lines need no candle machinery. No legend (that pyqtgraph version's `LegendItem` has
an initialisation-order bug, as `_report_comparison_chart_widget.py` records); the labels under the
plot name the two lines in their colours' words.
"""

from __future__ import annotations

from collections.abc import Sequence

from pyqtgraph import (  # type: ignore[import-untyped]
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
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.zoned_date_axis import (
    ZonedDateAxisItem,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
)

KEY_TEXT = "Green: the bot's equity. Grey: buy and hold, from the same capital."


class EquityPane(QWidget):
    """@brief Two curves: the bot and buy-and-hold, value at each close."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plot = PlotWidget(
            axisItems={"bottom": ZonedDateAxisItem(DEFAULT_TIMEZONE)}
        )
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

    def follow_display_timezone(self, preference: DisplayTimezonePreference) -> None:
        """@brief The time axis reads in the shared display time zone (`BUG-243`), now and after
        each change, until this pane is destroyed."""
        self._read_in_zone(preference.zone)
        self.destroyed.connect(preference.subscribe(self._read_in_zone))

    def _read_in_zone(self, zone: str) -> None:
        axis = self.plot.getPlotItem().getAxis("bottom")
        if isinstance(axis, ZonedDateAxisItem):
            axis.set_display_zone(zone)

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
