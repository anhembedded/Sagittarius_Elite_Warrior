from datetime import datetime, timezone

import pyqtgraph as pg
from PySide6 import QtCore


class CrosshairController:
    """
    @brief Synchronizes crosshair lines and the hover-info label across all registered plots.
    @details Single Responsibility: mouse-tracking/crosshair rendering only. Depends on a Qt
    scene and a label item (abstractions it is handed), not on ChartCard or ChartPlotLayout.
    """

    LINE_PEN = pg.mkPen(color="#aaaaaa", style=QtCore.Qt.DashLine)

    def __init__(self, scene: QtCore.QObject, label: pg.LabelItem) -> None:
        self._label = label
        self._plots: list[pg.PlotItem] = []
        self._v_lines: list[pg.InfiniteLine] = []
        self._h_lines: list[pg.InfiniteLine] = []

        # High-Performance Throttled Mouse Proxy (60 fps limit)
        self.proxy = pg.SignalProxy(
            scene.sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved
        )

    def register_plot(self, plot: pg.PlotItem) -> None:
        """Attaches a hidden crosshair line pair to a plot (main or subplot)."""
        v_line = pg.InfiniteLine(angle=90, movable=False, pen=self.LINE_PEN)
        h_line = pg.InfiniteLine(angle=0, movable=False, pen=self.LINE_PEN)
        v_line.hide()
        h_line.hide()

        plot.addItem(v_line, ignoreBounds=True)
        plot.addItem(h_line, ignoreBounds=True)

        self._plots.append(plot)
        self._v_lines.append(v_line)
        self._h_lines.append(h_line)

    def handle_mouse_moved(self, evt) -> None:
        """Public entry point mirroring the SignalProxy slot (used directly by tests)."""
        self._on_mouse_moved(evt)

    def _on_mouse_moved(self, evt) -> None:
        pos = evt[0]
        hovered = False

        for i, plot in enumerate(self._plots):
            if not plot.sceneBoundingRect().contains(pos):
                self._h_lines[i].hide()
                continue

            hovered = True
            mouse_point = plot.vb.mapSceneToView(pos)
            x_val, y_val = mouse_point.x(), mouse_point.y()

            # Show & update horizontal line ONLY for the hovered plot
            self._h_lines[i].setPos(y_val)
            self._h_lines[i].show()

            # Update ALL vertical lines across all plots to stay in sync
            for v_line in self._v_lines:
                v_line.setPos(x_val)
                v_line.show()

            self._update_label(x_val, y_val)

        if not hovered:
            for v_line in self._v_lines:
                v_line.hide()
            self._label.setText("Hover to see data")

    def _update_label(self, x_val: float, y_val: float) -> None:
        dt_str = datetime.fromtimestamp(x_val, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self._label.setText(
            f"<span style='color: #aaaaaa'>Time:</span> <span style='color: #ffffff'>{dt_str}</span> | "
            f"<span style='color: #aaaaaa'>Value:</span> <span style='color: #26a69a'>{y_val:.4f}</span>"
        )

    def dispose(self) -> None:
        if self.proxy:
            self.proxy.disconnect()
            self.proxy = None
        self._plots.clear()
        self._v_lines.clear()
        self._h_lines.clear()
