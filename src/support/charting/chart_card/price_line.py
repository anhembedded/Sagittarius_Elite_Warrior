import pyqtgraph as pg
from PySide6 import QtCore
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

from . import theme

#: Where a horizontal line's tag holds on its text, for the line's two label
#: positions (`BUG-176`). pyqtgraph centres the text on the position, so a tag
#: at the right edge (`position` 1.0) had half of itself outside the plot's view
#: box, which clips its children: "2,565.43" showed as "2,56". `(1, y)` puts the
#: tag's right edge on the position, inside the plot at any width. Every tag
#: that sits at the right edge uses this one pair.
RIGHT_EDGE_TAG_ANCHORS = [(1.0, 0.0), (1.0, 1.0)]


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
            label="",
            labelOpts={
                "position": 1.0,
                "anchors": RIGHT_EDGE_TAG_ANCHORS,
                "color": theme.PRICE_LEVEL_LABEL_COLOR,
                "fill": pg.mkBrush(theme.BULL_COLOR),
                "movable": False,
            },
        )
        self._line.hide()
        plot.addItem(self._line, ignoreBounds=True)

    @property
    def item(self) -> pg.InfiniteLine:
        """The line on the plot, so a caller can tell it from its own lines."""
        return self._line

    def update_price(self, price: float, is_bullish: bool) -> None:
        color = theme.BULL_COLOR if is_bullish else theme.BEAR_COLOR
        self._line.setPen(pg.mkPen(color, width=1, style=QtCore.Qt.DashLine))
        self._line.label.fill = pg.mkBrush(color)
        self._line.label.update()
        # pyqtgraph writes the label with `format.format(value=...)`; the text
        # is the formatter's, so it is the whole format and holds no field.
        self._line.label.setFormat(
            write_value(ColumnKind.PRICE, price).replace("{", "{{").replace("}", "}}")
        )
        self._line.setPos(price)
        self._line.show()
        self._line.label.valueChanged()

    def hide(self) -> None:
        self._line.hide()
