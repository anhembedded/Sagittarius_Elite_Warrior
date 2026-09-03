import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets


class ZoomControls(QtCore.QObject):
    """
    @brief Floating zoom buttons so zooming the chart never depends on having a scroll
    wheel (trackpads, wheel-less mice). Complements the existing wheel/right-drag zoom
    gestures — does not replace them.
    @details Single Responsibility: renders + positions the buttons and translates clicks
    into ViewBox calls:
    - Horizontal (H+/H−): scales the X axis only. Y keeps auto-ranging to the visible
      candles, same as wheel zoom already does.
    - Vertical (V+/V−): scales the Y axis only. pyqtgraph's setYRange() disables Y
      auto-range as a side effect (its default `disableAutoRange=True`), which is exactly
      what we want — reset re-enables it.
    - Box (▭): toggles the ViewBox into RectMode so the next left-drag draws a rubber-band
      rectangle and zooms into it (both axes) — pyqtgraph's own built-in gesture, not
      hand-rolled. Reverts to normal pan mode after one use.
    - Reset (↺): fits the full data range and re-enables Y auto-follow.
    """

    _MARGIN = 12
    # Must fit "H+"/"H−"/"V+"/"V−" (24px wide under the app's dark QSS font) plus that
    # stylesheet's QToolButton { padding: 3px } on each side — 24 was eliding to "...".
    _BUTTON_SIZE = 32
    _GAP = 4
    _ZOOM_IN_FACTOR = 0.85
    _ZOOM_OUT_FACTOR = 1.0 / 0.85
    #: `ChartPlotLayout` reserves row 0 for the crosshair readout
    #: (`crosshair_label`), a single line of text whose *row height* is
    #: fixed regardless of canvas size (only its *width* grows with the
    #: hovered point's text) — measured identically at canvas heights
    #: 173px and 700px: `main_plot`'s own viewbox starts at y=41 either
    #: way. Anchoring the button cluster's top there instead of the
    #: original y=12 clears row 0 unconditionally (not just for the one
    #: canvas size a bug report happened to show), landing the cluster on
    #: the candlestick plot area itself — floating over plotted data is
    #: the normal, accepted trade-off this kind of control makes
    #: everywhere; the bug was specifically overlapping *text*.
    _TOP_CLEARANCE = 40
    #: Below this canvas height, the 6-button cluster is hidden entirely
    #: rather than positioned — measured on the Trading screen's equity
    #: mini-chart (~173px tall): even anchored below `_TOP_CLEARANCE`,
    #: `main_plot`'s own viewbox is only ~49px tall there, nowhere near
    #: this cluster's 104px, and the next content down (the volume
    #: subplot + its own X-axis) starts immediately after — there is no
    #: 104px span left anywhere free of either plotted axis text or the
    #: candlesticks squeezed to illegibility behind the buttons. Wheel/
    #: right-drag zoom (this class's own docstring: "complements ... does
    #: not replace") stays fully available either way, so hiding costs no
    #: functionality.
    _MIN_CANVAS_HEIGHT_FOR_CONTROLS = 220

    def __init__(self, plot: pg.PlotItem, canvas: QtWidgets.QWidget) -> None:
        super().__init__()
        self._plot = plot
        self._canvas = canvas

        self._h_in_btn = self._make_button("H+", "Zoom in horizontally", canvas)
        self._h_out_btn = self._make_button("H−", "Zoom out horizontally", canvas)
        self._v_in_btn = self._make_button("V+", "Zoom in vertically", canvas)
        self._v_out_btn = self._make_button("V−", "Zoom out vertically", canvas)
        self._box_btn = self._make_button("▭", "Box zoom: drag a rectangle", canvas)
        self._box_btn.setCheckable(True)
        self._reset_btn = self._make_button("↺", "Reset zoom", canvas)

        self._h_in_btn.clicked.connect(lambda: self._zoom(x=self._ZOOM_IN_FACTOR))
        self._h_out_btn.clicked.connect(lambda: self._zoom(x=self._ZOOM_OUT_FACTOR))
        self._v_in_btn.clicked.connect(lambda: self._zoom(y=self._ZOOM_IN_FACTOR))
        self._v_out_btn.clicked.connect(lambda: self._zoom(y=self._ZOOM_OUT_FACTOR))
        self._box_btn.toggled.connect(self._set_box_zoom_active)
        self._reset_btn.clicked.connect(self._reset)

        self._plot.vb.sigRangeChangedManually.connect(self._on_manual_range_change)

        canvas.installEventFilter(self)
        self._reposition()

    @staticmethod
    def _make_button(
        text: str, tooltip: str, parent: QtWidgets.QWidget
    ) -> QtWidgets.QToolButton:
        btn = QtWidgets.QToolButton(parent)
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setFixedSize(ZoomControls._BUTTON_SIZE, ZoomControls._BUTTON_SIZE)
        return btn

    def _zoom(self, x: float | None = None, y: float | None = None) -> None:
        self._plot.vb.scaleBy(x=x, y=y)

    def _set_box_zoom_active(self, active: bool) -> None:
        self._plot.vb.setMouseMode(
            pg.ViewBox.RectMode if active else pg.ViewBox.PanMode
        )

    def _on_manual_range_change(self, *_args) -> None:
        """Box zoom is a one-shot tool: revert to normal pan mode after a single drag."""
        if self._box_btn.isChecked():
            self._box_btn.setChecked(False)

    def _reset(self) -> None:
        # Order matters: autoRange() -> setRange() disables autorange as a side effect
        # (its default disableAutoRange=True), so re-enable it AFTER fitting the view,
        # not before — otherwise this call would immediately undo itself.
        self._plot.autoRange()
        self._plot.vb.enableAutoRange(axis="y", enable=True)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._canvas and event.type() == QtCore.QEvent.Type.Resize:
            self._reposition()
        return False

    def _reposition(self) -> None:
        # 2-column grid: (H+, H−) / (V+, V−) / (▭, ↺)
        rows = (
            (self._h_in_btn, self._h_out_btn),
            (self._v_in_btn, self._v_out_btn),
            (self._box_btn, self._reset_btn),
        )
        all_buttons = [btn for row in rows for btn in row]

        if self._canvas.height() < self._MIN_CANVAS_HEIGHT_FOR_CONTROLS:
            for btn in all_buttons:
                btn.hide()
            return
        for btn in all_buttons:
            btn.show()

        for row_idx, (left_btn, right_btn) in enumerate(rows):
            y = self._TOP_CLEARANCE + row_idx * (self._BUTTON_SIZE + self._GAP)
            left_btn.move(self._MARGIN, y)
            right_btn.move(self._MARGIN + self._BUTTON_SIZE + self._GAP, y)
            left_btn.raise_()
            right_btn.raise_()

    def dispose(self) -> None:
        self._canvas.removeEventFilter(self)
        for btn in (
            self._h_in_btn,
            self._h_out_btn,
            self._v_in_btn,
            self._v_out_btn,
            self._box_btn,
            self._reset_btn,
        ):
            btn.deleteLater()
