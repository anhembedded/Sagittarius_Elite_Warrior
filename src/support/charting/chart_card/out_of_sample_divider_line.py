import pyqtgraph as pg
from PySide6 import QtCore

from .theme import CROSSHAIR_COLOR


class OutOfSampleDividerLine:
    """
    @brief `BOT-107A` — a persistent dashed vertical line marking where a
    static backtest's in-sample (tuning) data ends and its out-of-sample
    (unseen) data begins.

    @details Single Responsibility, same split as `TradeLinkLine` in this
    package: tracks and renders exactly one marker, no knowledge of
    `BacktestResult`/`OutOfSampleValidation`, both of which stay in
    `modules/backtesting/ui/`. Uses the same muted colour as the crosshair
    (`CROSSHAIR_COLOR`) rather than a bull/bear/accent one — this line is
    structural, not a trading fact.
    """

    def __init__(self, plot: pg.PlotItem) -> None:
        self._line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(CROSSHAIR_COLOR, width=1, style=QtCore.Qt.DashLine),
        )
        self._line.hide()
        plot.addItem(self._line, ignoreBounds=True)

    def show_at(self, split_timestamp: float) -> None:
        self._line.setPos(split_timestamp)
        self._line.show()

    def hide(self) -> None:
        self._line.hide()
