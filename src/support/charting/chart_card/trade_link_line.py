import pyqtgraph as pg
from PySide6 import QtCore


class TradeLinkLine:
    """
    @brief `PROP-001` — a dashed line connecting one trade's entry and exit
    points, shown while its row is selected in the Trade Logs table.

    @details Single Responsibility, same split as `LastPriceLine` in this
    package: tracks and renders one connecting segment — no knowledge of
    `Trade`, the table, or selection state, all of which stay in
    `modules/backtesting/ui/`. At most one is ever visible at a time
    (`PROP-001` §3.2's own performance note), so this owns exactly one
    curve and one label rather than a keyed collection.
    """

    def __init__(self, plot: pg.PlotItem) -> None:
        self._curve = pg.PlotDataItem()
        self._curve.hide()
        plot.addItem(self._curve, ignoreBounds=True)
        self._label = pg.TextItem(anchor=(0.5, 1.0))
        self._label.hide()
        plot.addItem(self._label, ignoreBounds=True)

    def show_link(
        self,
        entry_point: tuple[float, float],
        exit_point: tuple[float, float],
        color: str,
        label_text: str,
    ) -> None:
        entry_x, entry_y = entry_point
        exit_x, exit_y = exit_point
        pen = pg.mkPen(color, width=2, style=QtCore.Qt.DashLine)
        self._curve.setData(x=[entry_x, exit_x], y=[entry_y, exit_y], pen=pen)
        self._curve.show()
        self._label.setText(label_text, color=color)
        self._label.setPos((entry_x + exit_x) / 2, max(entry_y, exit_y))
        self._label.show()

    def hide(self) -> None:
        self._curve.hide()
        self._label.hide()
