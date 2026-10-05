"""A chart's zoom commands as actions (`EPIC-033G`).

Zooming never needs a scroll wheel: Zoom in, Zoom out, Box zoom and Reset zoom
sit on the chart's toolbar, and those four plus the two vertical zooms are in
the plot's context menu, beside pyqtgraph's own entries. They replace
`ZoomControls`, six fixed-size buttons positioned over the plot with `move()`,
which covered the price axis and hid below a 220 px canvas
(`ui-presentation-rule.md` §3: no widget placed over another). The wheel and
drag gestures are pyqtgraph's and are unchanged; a double-click on the plot
triggers Reset zoom, as it does in every trading terminal (pyqtgraph has no
such gesture of its own).

What each does, unchanged from `ZoomControls`:
- Zoom in/out scales the X axis only; Y keeps auto-ranging to the visible
  candles, as the wheel does.
- The vertical zooms scale the Y axis only. pyqtgraph's `scaleBy` turns Y
  auto-range off as a side effect, which is what a vertical zoom means; Reset
  turns it back on.
- Box zoom puts the view box in `RectMode` for one drag: the next left-drag
  draws a rectangle and zooms into it, then it reverts to panning.
- Reset fits the whole data range and re-enables Y auto-follow.
"""

from __future__ import annotations

import pyqtgraph as pg
from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction

_ZOOM_IN_FACTOR = 0.85
_ZOOM_OUT_FACTOR = 1.0 / 0.85


class ChartZoomActions(QObject):
    """The zoom actions of one plot; they live as long as the chart."""

    def __init__(self, plot: pg.PlotItem, parent: QObject) -> None:
        super().__init__(parent)
        self._plot = plot
        self.zoom_in = self._action("Zoom &in", "zoomIn", "Zoom in horizontally")
        self.zoom_out = self._action("Zoom &out", "zoomOut", "Zoom out horizontally")
        self.zoom_in_vertically = self._action(
            "Zoom in &vertically", "zoomInVertically", "Zoom in on the price axis"
        )
        self.zoom_out_vertically = self._action(
            "Zoom out verticall&y", "zoomOutVertically", "Zoom out on the price axis"
        )
        self.box_zoom = self._action(
            "&Box zoom", "boxZoom", "Drag a rectangle to zoom into it"
        )
        self.box_zoom.setCheckable(True)
        self.reset_zoom = self._action(
            "&Reset zoom", "resetZoom", "Fit the whole history and follow the price"
        )
        self.zoom_in.triggered.connect(lambda: self._scale(x=_ZOOM_IN_FACTOR))
        self.zoom_out.triggered.connect(lambda: self._scale(x=_ZOOM_OUT_FACTOR))
        self.zoom_in_vertically.triggered.connect(
            lambda: self._scale(y=_ZOOM_IN_FACTOR)
        )
        self.zoom_out_vertically.triggered.connect(
            lambda: self._scale(y=_ZOOM_OUT_FACTOR)
        )
        self.box_zoom.toggled.connect(self._set_box_zoom)
        self.reset_zoom.triggered.connect(self._reset)
        plot.vb.sigRangeChangedManually.connect(self._end_box_zoom)
        plot.scene().sigMouseClicked.connect(self._reset_on_double_click)
        self._add_to_context_menu()

    @property
    def toolbar_actions(self) -> tuple[QAction, ...]:
        """What the chart's toolbar shows; the vertical zooms are menu-only."""
        return (self.zoom_in, self.zoom_out, self.box_zoom, self.reset_zoom)

    @property
    def all_actions(self) -> tuple[QAction, ...]:
        return (
            self.zoom_in,
            self.zoom_out,
            self.zoom_in_vertically,
            self.zoom_out_vertically,
            self.box_zoom,
            self.reset_zoom,
        )

    def _action(self, text: str, name: str, tooltip: str) -> QAction:
        action = QAction(text, self)
        action.setObjectName(f"act_{name}")
        action.setToolTip(tooltip)
        return action

    def _add_to_context_menu(self) -> None:
        """Every toolbar action is also in a menu (MS `cmd-toolbars`): here,
        the plot's own context menu, after pyqtgraph's entries."""
        menu = self._plot.vb.menu
        menu.addSeparator()
        for action in self.all_actions:
            menu.addAction(action)

    def _scale(self, x: float | None = None, y: float | None = None) -> None:
        self._plot.vb.scaleBy(x=x, y=y)

    def _set_box_zoom(self, active: bool) -> None:
        self._plot.vb.setMouseMode(
            pg.ViewBox.RectMode if active else pg.ViewBox.PanMode
        )

    def _end_box_zoom(self, *_args: object) -> None:
        """Box zoom is a one-shot tool: back to panning after a single drag."""
        if self.box_zoom.isChecked():
            self.box_zoom.setChecked(False)

    def _reset_on_double_click(self, event: MouseClickEvent) -> None:
        if event.double() and self._plot.vb.sceneBoundingRect().contains(
            event.scenePos()
        ):
            self.reset_zoom.trigger()

    def _reset(self) -> None:
        # Order matters: autoRange() disables Y auto-range as a side effect, so
        # re-enable it after fitting the view, not before.
        self._plot.autoRange()
        self._plot.vb.enableAutoRange(axis="y", enable=True)
