from collections.abc import Callable
from datetime import UTC, datetime

import pyqtgraph as pg
from PySide6 import QtCore, QtGui
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    AppValueFormatter,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    FormatContext,
)

from .chart_chrome import ChartChrome

OhlcCandle = tuple[float, float, float, float, float]


class CrosshairController:
    """
    @brief Synchronizes crosshair lines across all registered plots and reports
    what is under the pointer.
    @details Single Responsibility: mouse-tracking/crosshair rendering only. Depends on a Qt
    scene, a readout callback and an optional OHLC lookup callback (abstractions it is
    handed), not on ChartCard, ChartPlotLayout or FastCandlestickItem directly. The
    readout is plain text, `""` once the pointer leaves; `ChartCard` puts it in the
    status bar (`EPIC-033G`), where it used to be a label row above the plot.
    Lines and axis tags are chrome: `set_chrome` repaints them when the palette
    changes (`chart_chrome.py`).
    """

    def __init__(
        self,
        scene: QtCore.QObject,
        on_readout: Callable[[str], None],
        ohlc_lookup: Callable[[float], OhlcCandle | None] | None = None,
        *,
        chrome: ChartChrome,
    ) -> None:
        self._chrome = chrome
        self._on_readout = on_readout
        self._ohlc_lookup = ohlc_lookup
        self._formatter = AppValueFormatter(DEFAULT_TIMEZONE)
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
        self._formatter = AppValueFormatter(tz_name)

    def register_plot(self, plot: pg.PlotItem, is_primary: bool = False) -> None:
        """Attaches a hidden crosshair line pair to a plot (main or subplot)."""
        if is_primary:
            self._primary_plot = plot

        v_line = pg.InfiniteLine(angle=90, movable=False, pen=self._line_pen())
        h_line = pg.InfiniteLine(angle=0, movable=False, pen=self._line_pen())
        v_line.hide()
        h_line.hide()

        x_label = self._new_tag()
        x_label.setAnchor((0.5, 1.0))
        x_label.hide()
        x_label.setZValue(1000)

        y_label = self._new_tag()
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

    def set_chrome(self, chrome: ChartChrome) -> None:
        """Repaints every line and tag in `chrome`'s colours."""
        self._chrome = chrome
        for line in (*self._v_lines, *self._h_lines):
            line.setPen(self._line_pen())
        for tag in (*self._x_labels, *self._y_labels):
            tag.fill = pg.mkBrush(chrome.tag_fill)
            tag.setColor(chrome.tag_text)

    def _line_pen(self) -> QtGui.QPen:
        return pg.mkPen(color=self._chrome.crosshair, style=QtCore.Qt.DashLine)

    def _new_tag(self) -> pg.TextItem:
        """An axis tag: the value under the pointer, on the axis."""
        return pg.TextItem(
            fill=pg.mkBrush(self._chrome.tag_fill), color=self._chrome.tag_text
        )

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
            y_html = f"<div style='font-size: 11px;'>{write_value(ColumnKind.PRICE, y_val)}</div>"
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
                dt_str = self._time_text(x_val)

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
            self._set_info_text("")

    def _update_label(self, x_val: float, y_val: float) -> None:
        self._set_info_text(
            f"Time: {self._time_text(x_val)}"
            f"   Value: {write_value(ColumnKind.PRICE, y_val)}"
        )

    def _update_ohlc_label(self, candle: OhlcCandle) -> None:
        """The change is the formatter's percent: a loss carries its minus, so
        the direction never depends on colour alone."""
        t, o, h, low, c = candle
        change_pct = ((c - o) / o * 100.0) if o else 0.0
        self._set_info_text(
            f"{self._time_text(t)}"
            f"   O {write_value(ColumnKind.PRICE, o)}"
            f"   H {write_value(ColumnKind.PRICE, h)}"
            f"   L {write_value(ColumnKind.PRICE, low)}"
            f"   C {write_value(ColumnKind.PRICE, c)}"
            f"   ({write_value(ColumnKind.PERCENT, change_pct)})"
        )

    def _time_text(self, timestamp: float) -> str:
        """A UNIX time in seconds as the formatter writes a timestamp, in this
        chart's display time zone; empty for one no datetime can hold."""
        try:
            moment = datetime.fromtimestamp(timestamp, tz=UTC)
        except (OSError, ValueError, OverflowError):
            return ""
        return self._formatter.format(
            ColumnKind.TIMESTAMP, moment, FormatContext(ColumnKind.TIMESTAMP.value)
        )

    def _set_info_text(self, text: str) -> None:
        if self._last_info_text == text:
            return
        self._on_readout(text)
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
