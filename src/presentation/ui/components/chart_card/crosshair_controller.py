from collections.abc import Callable

import pyqtgraph as pg
from PySide6 import QtCore
from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_timestamp,
)

from . import theme

OhlcCandle = tuple[float, float, float, float, float]


class CrosshairController:
    """
    @brief Synchronizes crosshair lines and the hover-info label across all registered plots.
    @details Single Responsibility: mouse-tracking/crosshair rendering only. Depends on a Qt
    scene, a label item, and an optional OHLC lookup callback (abstractions it is handed),
    not on ChartCard, ChartPlotLayout or FastCandlestickItem directly.
    """

    LINE_PEN = pg.mkPen(color=theme.CROSSHAIR_COLOR, style=QtCore.Qt.DashLine)

    def __init__(
        self,
        scene: QtCore.QObject,
        label: pg.LabelItem,
        ohlc_lookup: Callable[[float], OhlcCandle | None] | None = None,
    ) -> None:
        self._label = label
        self._ohlc_lookup = ohlc_lookup
        self._display_timezone: str = DEFAULT_TIMEZONE
        self._primary_plot: pg.PlotItem | None = None
        self._plots: list[pg.PlotItem] = []
        self._v_lines: list[pg.InfiniteLine] = []
        self._h_lines: list[pg.InfiniteLine] = []
        self._x_labels: list[pg.TextItem] = []
        self._y_labels: list[pg.TextItem] = []

        # High-Performance Throttled Mouse Proxy (60 fps limit)
        self.proxy = pg.SignalProxy(
            scene.sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved
        )

    def set_display_timezone(self, tz_name: str) -> None:
        """Sets the display timezone used for timestamps."""
        self._display_timezone = tz_name

    def register_plot(self, plot: pg.PlotItem, is_primary: bool = False) -> None:
        """Attaches a hidden crosshair line pair to a plot (main or subplot)."""
        if is_primary:
            self._primary_plot = plot

        v_line = pg.InfiniteLine(angle=90, movable=False, pen=self.LINE_PEN)
        h_line = pg.InfiniteLine(angle=0, movable=False, pen=self.LINE_PEN)
        v_line.hide()
        h_line.hide()

        # We use HTML/CSS inside TextItem for background styling.
        # fill is not strictly needed if we style the HTML background, but it sets the item background.
        x_label = pg.TextItem(fill=pg.mkBrush("#2b3139"), color="w")
        x_label.hide()
        x_label.setZValue(1000)

        y_label = pg.TextItem(fill=pg.mkBrush("#2b3139"), color="w")
        y_label.hide()
        y_label.setZValue(1000)

        plot.addItem(v_line, ignoreBounds=True)
        plot.addItem(h_line, ignoreBounds=True)
        plot.addItem(x_label, ignoreBounds=True)
        plot.addItem(y_label, ignoreBounds=True)

        self._plots.append(plot)
        self._v_lines.append(v_line)
        self._h_lines.append(h_line)
        self._x_labels.append(x_label)
        self._y_labels.append(y_label)

    def unregister_plot(self, plot: pg.PlotItem) -> None:
        """
        @brief Detaches the crosshair line pair previously attached via
        register_plot.
        @details Needed whenever a subplot row itself is removed (e.g. an
        indicator being deregistered before rebuild) — otherwise
        _on_mouse_moved keeps iterating over a PlotItem no longer in the
        layout/scene.
        """
        if plot not in self._plots:
            return
        idx = self._plots.index(plot)
        self._plots.pop(idx)
        v_line = self._v_lines.pop(idx)
        h_line = self._h_lines.pop(idx)
        x_label = self._x_labels.pop(idx)
        y_label = self._y_labels.pop(idx)

        plot.removeItem(v_line)
        plot.removeItem(h_line)
        plot.removeItem(x_label)
        plot.removeItem(y_label)

        if plot is self._primary_plot:
            self._primary_plot = None

    def handle_mouse_moved(self, evt) -> None:
        """Public entry point mirroring the SignalProxy slot (used directly by tests)."""
        self._on_mouse_moved(evt)

    def _on_mouse_moved(self, evt) -> None:
        pos = evt[0]
        hovered = False

        # Hide X labels on all plots first
        for x_label in self._x_labels:
            x_label.hide()

        for i, plot in enumerate(self._plots):
            if not plot.sceneBoundingRect().contains(pos):
                self._h_lines[i].hide()
                self._y_labels[i].hide()
                continue

            hovered = True
            mouse_point = plot.vb.mapSceneToView(pos)
            x_val, y_val = mouse_point.x(), mouse_point.y()

            view_range = plot.vb.viewRange()
            x_min = view_range[0][0]

            # Show & update horizontal line ONLY for the hovered plot
            self._h_lines[i].setPos(y_val)
            self._h_lines[i].show()

            # Show Y label on the left edge (x_min)
            self._y_labels[i].setPos(x_min, y_val)
            self._y_labels[i].setHtml(
                f"<div style='font-size: 11px;'>{y_val:.4f}</div>"
            )
            self._y_labels[i].setAnchor((0.0, 0.5))
            self._y_labels[i].show()

            # Update ALL vertical lines across all plots to stay in sync
            for v_line in self._v_lines:
                v_line.setPos(x_val)
                v_line.show()

            # Show X label only on the bottom-most plot
            if self._plots:
                bottom_plot = self._plots[-1]
                bottom_y_min = bottom_plot.vb.viewRange()[1][0]
                dt_str = format_display_timestamp(x_val, tz_name=self._display_timezone)

                self._x_labels[-1].setPos(x_val, bottom_y_min)
                self._x_labels[-1].setHtml(
                    f"<div style='font-size: 11px;'>{dt_str}</div>"
                )
                self._x_labels[-1].setAnchor((0.5, 1.0))
                self._x_labels[-1].show()

            candle = None
            if plot is self._primary_plot and self._ohlc_lookup:
                candle = self._ohlc_lookup(x_val)

            if candle is not None:
                self._update_ohlc_label(candle)
            else:
                self._update_label(x_val, y_val)

        if not hovered:
            for v_line in self._v_lines:
                v_line.hide()
            self._label.setText("Hover to see data")

    def _update_label(self, x_val: float, y_val: float) -> None:
        dt_str = format_display_timestamp(x_val, tz_name=self._display_timezone)
        self._label.setText(
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>Time:</span> <span style='color: #ffffff'>{dt_str}</span> | "
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>Value:</span> <span style='color: {theme.BULL_COLOR}'>{y_val:.4f}</span>"
        )

    def _update_ohlc_label(self, candle: OhlcCandle) -> None:
        t, o, h, low, c = candle
        change_pct = ((c - o) / o * 100.0) if o else 0.0
        change_color = theme.BULL_COLOR if c >= o else theme.BEAR_COLOR
        dt_str = format_display_timestamp(t, tz_name=self._display_timezone)
        self._label.setText(
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>{dt_str}</span> &nbsp; "
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>O</span> <span style='color: #ffffff'>{o:.4f}</span> "
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>H</span> <span style='color: #ffffff'>{h:.4f}</span> "
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>L</span> <span style='color: #ffffff'>{low:.4f}</span> "
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>C</span> <span style='color: #ffffff'>{c:.4f}</span> "
            f"<span style='color: {change_color}'>({change_pct:+.2f}%)</span>"
        )

    def dispose(self) -> None:
        if self.proxy:
            self.proxy.disconnect()
            self.proxy = None
        self._plots.clear()
        self._v_lines.clear()
        self._h_lines.clear()
        self._x_labels.clear()
        self._y_labels.clear()
        self._primary_plot = None
