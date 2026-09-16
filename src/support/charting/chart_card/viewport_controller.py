import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets


class ViewportController(QtCore.QObject):
    """
    @brief Tracks whether the chart should auto-follow the newest candle (the default,
    TradingView-style "live" behavior) or stay frozen wherever the user panned/zoomed to,
    and shows a floating "Jump to Live" button once the user has scrolled away.
    @details Single Responsibility: follow-state + the button's visibility/position. Uses
    ViewBox.sigRangeChangedManually — emitted only on user-driven pan/zoom, never on the
    programmatic setXRange() this class itself performs — so it never fights the user.
    """

    _MARGIN = 12

    def __init__(self, plot: pg.PlotItem, canvas: QtWidgets.QWidget) -> None:
        super().__init__()
        self._plot = plot
        self._canvas = canvas
        self._following = True

        self._button = QtWidgets.QPushButton("⏩ Live", canvas)
        self._button.setCursor(QtCore.Qt.PointingHandCursor)
        self._button.hide()
        self._button.clicked.connect(self.resume_follow)

        plot.vb.sigRangeChangedManually.connect(self._on_user_panned)
        canvas.installEventFilter(self)

    def notify_new_data(self, latest_timestamp: float) -> None:
        """Called after every historical render / live tick to re-center the view."""
        if not self._following:
            return
        (x_min, x_max), _ = self._plot.vb.viewRange()
        span = x_max - x_min
        self._plot.setXRange(latest_timestamp - span, latest_timestamp, padding=0)

    def resume_follow(self) -> None:
        self._following = True
        self._button.hide()

    def _on_user_panned(self, *_args) -> None:
        self._following = False
        self._reposition()
        self._button.show()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._canvas and event.type() == QtCore.QEvent.Type.Resize:
            self._reposition()
        return False

    def _reposition(self) -> None:
        x = self._canvas.width() - self._button.sizeHint().width() - self._MARGIN
        y = self._canvas.height() - self._button.sizeHint().height() - self._MARGIN
        self._button.move(max(0, x), max(0, y))

    def dispose(self) -> None:
        self._canvas.removeEventFilter(self)
        self._button.deleteLater()
