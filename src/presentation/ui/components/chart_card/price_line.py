import pyqtgraph as pg
from PySide6 import QtCore
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette

from . import theme


class LastPriceLine:
    """
    @brief TradingView-style horizontal line pinned to the latest close price, with an
    inline price tag on the line, colored by candle direction.
    @details Single Responsibility: tracks and renders one value (the last price) — no
    knowledge of candlestick data structures or crosshair state.
    """

    def __init__(self, plot: pg.PlotItem) -> None:
        self._line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(theme.BULL_COLOR, width=1, style=QtCore.Qt.DashLine),
            label="{value:.4f}",
            labelOpts={
                "position": 1.0,
                "color": Palette.TEXT_PRIMARY,
                "fill": pg.mkBrush(theme.BULL_COLOR),
                "movable": False,
            },
        )
        self._line.hide()
        plot.addItem(self._line, ignoreBounds=True)

    def update_price(self, price: float, is_bullish: bool) -> None:
        color = theme.BULL_COLOR if is_bullish else theme.BEAR_COLOR
        self._line.setPen(pg.mkPen(color, width=1, style=QtCore.Qt.DashLine))
        self._line.label.fill = pg.mkBrush(color)
        self._line.label.update()
        self._line.setPos(price)
        self._line.show()

    def hide(self) -> None:
        self._line.hide()
