from collections.abc import Callable

import pyqtgraph as pg
from PySide6 import QtCore
from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_timestamp,
)

from . import theme

#: Crosshair readout label background.
_LABEL_FILL = "#2b3139"  # token-exempt: chart_card avoids Palette, see theme.py

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
        self._last_x_label_html: str | None = None
        self._last_y_label_html: list[str | None] = []
        self._last_info_text: str | None = None
        self._suspended = False

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
        x_label = pg.TextItem(
            fill=pg.mkBrush(_LABEL_FILL),
            color="w",
        )
        x_label.setAnchor((0.5, 1.0))
        x_label.hide()
        x_label.setZValue(1000)

        y_label = pg.TextItem(
            fill=pg.mkBrush(_LABEL_FILL),
            color="w",
        )
        y_label.setAnchor((0.0, 0.5))
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
        self._last_y_label_html.append(None)
        self._last_x_label_html = None

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
        self._last_y_label_html.pop(idx)
        self._last_x_label_html = None

        plot.removeItem(v_line)
        plot.removeItem(h_line)
        plot.removeItem(x_label)
        plot.removeItem(y_label)

        if plot is self._primary_plot:
            self._primary_plot = None

    def handle_mouse_moved(self, evt) -> None:
        """Public entry point mirroring the SignalProxy slot (used directly by tests)."""
        if self._suspended:
            return
        self._on_mouse_moved(evt)

    def set_suspended(self, suspended: bool) -> None:
        """Hide scene crosshair items while a cached frame owns interaction."""
        self._suspended = bool(suspended)
        if not suspended:
            return
        items = (*self._v_lines, *self._h_lines, *self._x_labels, *self._y_labels)
        for item in items:
            self._hide_if_visible(item)

    def _on_mouse_moved(self, evt) -> None:
        pos = evt[0]
        hovered = False

        for i, plot in enumerate(self._plots):
            if not plot.sceneBoundingRect().contains(pos):
                self._hide_if_visible(self._h_lines[i])
                self._hide_if_visible(self._y_labels[i])
                continue

            hovered = True
            mouse_point = plot.vb.mapSceneToView(pos)
            x_val, y_val = mouse_point.x(), mouse_point.y()

            view_range = plot.vb.viewRange()
            x_min = view_range[0][0]

            # Show & update horizontal line ONLY for the hovered plot
            self._h_lines[i].setPos(y_val)
            self._show_if_hidden(self._h_lines[i])

            # Show Y label on the left edge (x_min)
            self._y_labels[i].setPos(x_min, y_val)
            y_html = f"<div style='font-size: 11px;'>{y_val:.4f}</div>"
            if self._last_y_label_html[i] != y_html:
                self._y_labels[i].setHtml(y_html)
                self._last_y_label_html[i] = y_html
            self._show_if_hidden(self._y_labels[i])

            # Update ALL vertical lines across all plots to stay in sync
            for v_line in self._v_lines:
                v_line.setPos(x_val)
                self._show_if_hidden(v_line)

            # Show X label only on the bottom-most plot
            if self._plots:
                bottom_plot = self._plots[-1]
                bottom_y_min = bottom_plot.vb.viewRange()[1][0]
                dt_str = format_display_timestamp(x_val, tz_name=self._display_timezone)

                x_label = self._x_labels[-1]
                x_label.setPos(x_val, bottom_y_min)
                x_html = f"<div style='font-size: 11px;'>{dt_str}</div>"
                if self._last_x_label_html != x_html:
                    x_label.setHtml(x_html)
                    self._last_x_label_html = x_html
                self._show_if_hidden(x_label)

            candle = None
            if plot is self._primary_plot and self._ohlc_lookup:
                candle = self._ohlc_lookup(x_val)

            if candle is not None:
                self._update_ohlc_label(candle)
            else:
                self._update_label(x_val, y_val)

        if not hovered:
            for v_line in self._v_lines:
                self._hide_if_visible(v_line)
            for x_label in self._x_labels:
                self._hide_if_visible(x_label)
            self._set_info_text("Hover to see data")

    def _update_label(self, x_val: float, y_val: float) -> None:
        dt_str = format_display_timestamp(x_val, tz_name=self._display_timezone)
        self._set_info_text(
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>Time:</span> <span style='color: #ffffff'>{dt_str}</span> | "  # token-exempt: chart_card avoids Palette, see theme.py
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>Value:</span> <span style='color: {theme.BULL_COLOR}'>{y_val:.4f}</span>"
        )

    def _update_ohlc_label(self, candle: OhlcCandle) -> None:
        t, o, h, low, c = candle
        change_pct = ((c - o) / o * 100.0) if o else 0.0
        change_color = theme.BULL_COLOR if c >= o else theme.BEAR_COLOR
        dt_str = format_display_timestamp(t, tz_name=self._display_timezone)
        self._set_info_text(
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>{dt_str}</span> &nbsp; "
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>O</span> <span style='color: #ffffff'>{o:.4f}</span> "  # token-exempt: chart_card avoids Palette, see theme.py
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>H</span> <span style='color: #ffffff'>{h:.4f}</span> "  # token-exempt: chart_card avoids Palette, see theme.py
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>L</span> <span style='color: #ffffff'>{low:.4f}</span> "  # token-exempt: chart_card avoids Palette, see theme.py
            f"<span style='color: {theme.CROSSHAIR_COLOR}'>C</span> <span style='color: #ffffff'>{c:.4f}</span> "  # token-exempt: chart_card avoids Palette, see theme.py
            f"<span style='color: {change_color}'>({change_pct:+.2f}%)</span>"
        )

    def _set_info_text(self, text: str) -> None:
        if self._last_info_text == text:
            return
        self._label.setText(text)
        self._last_info_text = text

    @staticmethod
    def _show_if_hidden(item: pg.GraphicsObject) -> None:
        if not item.isVisible():
            item.show()

    @staticmethod
    def _hide_if_visible(item: pg.GraphicsObject) -> None:
        if item.isVisible():
            item.hide()

    def dispose(self) -> None:
        if self.proxy:
            self.proxy.disconnect()
            self.proxy = None
        self._plots.clear()
        self._v_lines.clear()
        self._h_lines.clear()
        self._x_labels.clear()
        self._y_labels.clear()
        self._last_y_label_html.clear()
        self._last_x_label_html = None
        self._last_info_text = None
        self._primary_plot = None
