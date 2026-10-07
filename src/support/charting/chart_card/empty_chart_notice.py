"""What a chart with no candles shows in place of its plot (`EPIC-034A`).

An empty `ChartCard` draws pyqtgraph's default axes: -50…50 and 1970-01-01 on
the owner's screen, which reads as a broken chart. The notice replaces the plot
with a sentence that names what is missing; the header, and so the timeframe
picker, stays, so the way out of an empty timeframe is still on screen.

The plot and the sentence are the two pages of a `QStackedWidget`, whose
minimum size is the larger of the two: an empty chart never has a lower floor
than the same chart with candles (the Bots mode's page floor test).
"""

from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.empty_page import empty_page

_OBJECT_NAME = "lblChartNoCandles"
_PLOT_PAGE, _NOTICE_PAGE = 0, 1


class EmptyChartNotice:
    """@brief Shows or clears the no-candles sentence on one `ChartCard`."""

    def __init__(self, card: ChartCard) -> None:
        plot = card.plot_layout.widget
        index = card.body_layout.indexOf(plot)
        card.body_layout.removeWidget(plot)
        self._page = empty_page("", _OBJECT_NAME)
        self._stack = QStackedWidget()
        self._stack.insertWidget(_PLOT_PAGE, plot)
        self._stack.insertWidget(_NOTICE_PAGE, self._page)
        card.body_layout.insertWidget(index, self._stack)

    def show(self, text: str) -> None:
        self._page.setText(text)
        self._stack.setCurrentIndex(_NOTICE_PAGE)

    def clear(self) -> None:
        self._stack.setCurrentIndex(_PLOT_PAGE)
