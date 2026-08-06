import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets


class ZoomControls(QtCore.QObject):
    """
    @brief Floating +/−/reset buttons so zooming the chart never depends on having a
    scroll wheel (trackpads, wheel-less mice). Complements the existing wheel/right-drag
    zoom gestures — does not replace them.
    @details Single Responsibility: renders + positions three buttons and translates
    clicks into ViewBox.scaleBy()/autoRange() calls on the X axis only (Y keeps
    auto-ranging to the visible candles, same as wheel zoom already does).
    """

    _MARGIN = 12
    _BUTTON_SIZE = 24
    _ZOOM_IN_FACTOR = 0.85
    _ZOOM_OUT_FACTOR = 1.0 / 0.85

    def __init__(self, plot: pg.PlotItem, canvas: QtWidgets.QWidget) -> None:
        super().__init__()
        self._plot = plot
        self._canvas = canvas

        self._zoom_in_btn = self._make_button("+", canvas)
        self._zoom_out_btn = self._make_button("−", canvas)
        self._reset_btn = self._make_button("↺", canvas)

        self._zoom_in_btn.clicked.connect(lambda: self._zoom(self._ZOOM_IN_FACTOR))
        self._zoom_out_btn.clicked.connect(lambda: self._zoom(self._ZOOM_OUT_FACTOR))
        self._reset_btn.clicked.connect(lambda: self._plot.autoRange())

        canvas.installEventFilter(self)
        self._reposition()

    @staticmethod
    def _make_button(text: str, parent: QtWidgets.QWidget) -> QtWidgets.QToolButton:
        btn = QtWidgets.QToolButton(parent)
        btn.setText(text)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setFixedSize(ZoomControls._BUTTON_SIZE, ZoomControls._BUTTON_SIZE)
        return btn

    def _zoom(self, factor: float) -> None:
        self._plot.vb.scaleBy(x=factor)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._canvas and event.type() == QtCore.QEvent.Type.Resize:
            self._reposition()
        return False

    def _reposition(self) -> None:
        buttons = (self._zoom_in_btn, self._zoom_out_btn, self._reset_btn)
        for i, btn in enumerate(buttons):
            btn.move(self._MARGIN, self._MARGIN + i * (self._BUTTON_SIZE + 4))
            btn.raise_()

    def dispose(self) -> None:
        self._canvas.removeEventFilter(self)
        for btn in (self._zoom_in_btn, self._zoom_out_btn, self._reset_btn):
            btn.deleteLater()
