from typing import Callable

import pyqtgraph as pg
from PySide6 import QtGui

from Binace_Bot.src.domain.indicator_scripts import InfoField

from .marker_layer import MarkerLayer, MarkerPoint
from .plot_layout import ChartPlotLayout
from .viewport_windowing import visible_slice_indices

#: Default text colour for an InfoField that didn't specify one.
_DEFAULT_INFO_COLOR = "#c9cdd3"
#: Drawn beneath candles/curves/volume so a background tint never occludes them.
_REGION_Z_VALUE = -10


class IndicatorManager:
    """
    @brief Adds, updates, toggles and removes overlay/subplot technical indicators
    (e.g. SMA, RSI, MACD), each with a TradingView-style legend entry.
    @details Single Responsibility: indicator curve lifecycle only. Depends on ChartPlotLayout
    (to place curves) and an injected callback (to keep new subplots crosshair-aware) rather
    than reaching into CrosshairController directly — Dependency Inversion.

    Legend click-to-toggle comes from pyqtgraph's own LegendItem/ItemSample (its swatch icon
    already toggles item visibility on click) — reused rather than hand-rolled, since it also
    handles corner-anchoring across pan/zoom correctly out of the box.

    Retains the full (x, y) series per indicator in `_full_data` and only pushes the
    slice inside the last-known visible X range to each curve's setData() — via
    `refresh_window()`, called by ChartCard on every pan/zoom. This is the same
    windowing pattern as FastCandlestickItem/VolumeItem (see their docstrings for why
    it matters), applied here once so it automatically covers every indicator added
    through this manager — including future strategy signal overlays — without each
    one needing its own perf work.
    """

    def __init__(
        self,
        plot_layout: ChartPlotLayout,
        on_new_plot: Callable[[pg.PlotItem], None],
        on_remove_plot: Callable[[pg.PlotItem], None] = lambda plot: None,
    ) -> None:
        self._plot_layout = plot_layout
        self._on_new_plot = on_new_plot
        self._on_remove_plot = on_remove_plot
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._plots: dict[str, pg.PlotItem] = {}
        self._legend_labels: dict[str, pg.LabelItem] = {}
        self._full_data: dict[str, tuple[list[float], list[float]]] = {}
        self._visible_range: tuple[float, float] | None = None

        # BOT-032 — custom indicator scripts' background tints and status
        # panel, each keyed by script registry key (not by line name: unlike
        # curves, a script has exactly one tint timeline and one status block,
        # not one per line).
        self._region_items: dict[str, list[pg.LinearRegionItem]] = {}
        self._script_info: dict[str, list[InfoField]] = {}
        self._marker_layer = MarkerLayer(self._plot_layout.main_plot)

    def add_overlay(self, name: str, color: str) -> None:
        """Adds a line indicator on top of the main candlestick plot (e.g. SMA)."""
        curve = self._plot_layout.main_plot.plot(
            pen=pg.mkPen(color=color, width=2), name=name
        )
        self._register(name, curve, self._plot_layout.main_plot)

    def add_subplot(self, name: str, color: str, height_ratio: int = 1) -> None:
        """Adds a separate subplot below the main chart (e.g. RSI, MACD, Volume)."""
        sub_plot = self._plot_layout.add_subplot(height_ratio=height_ratio)
        curve = sub_plot.plot(pen=pg.mkPen(color=color, width=2), name=name)
        self._register(name, curve, sub_plot)
        self._on_new_plot(sub_plot)

    def _register(self, name: str, curve: pg.PlotDataItem, plot: pg.PlotItem) -> None:
        self._curves[name] = curve
        self._plots[name] = plot

        legend = plot.addLegend()
        legend.addItem(curve, name)
        self._legend_labels[name] = legend.items[-1][1]

    def update_data(self, name: str, x_data: list[float], y_data: list[float]) -> None:
        """Updates the data arrays for a specific indicator and its legend value."""
        if name not in self._curves:
            return
        self._full_data[name] = (x_data, y_data)
        self._apply_window(name)
        if y_data:
            self._legend_labels[name].setText(f"{name}: {y_data[-1]:.4f}")

    def refresh_window(self, min_x: float, max_x: float) -> None:
        """
        @brief Re-applies just the points inside the visible X range to every
        registered indicator curve. Called by ChartCard whenever the chart's
        viewport changes (pan/zoom).
        """
        self._visible_range = (min_x, max_x)
        for name in self._curves:
            self._apply_window(name)

    def _apply_window(self, name: str) -> None:
        full = self._full_data.get(name)
        curve = self._curves.get(name)
        if full is None or curve is None:
            return
        x_data, y_data = full

        if self._visible_range is None or not x_data:
            curve.setData(x=x_data, y=y_data)
            return

        min_x, max_x = self._visible_range
        # Unlike candles/bars, indicator points have no natural "width" to
        # pad by — keep 1 extra point on each side of the bisected window so
        # the line connecting into view doesn't visibly end right at the edge.
        lo, hi = visible_slice_indices(x_data, min_x, max_x)
        lo = max(0, lo - 1)
        hi = min(len(x_data), hi + 1)
        curve.setData(x=x_data[lo:hi], y=y_data[lo:hi])

    def set_visible(self, name: str, visible: bool) -> None:
        """Programmatic equivalent of clicking the legend swatch (same underlying state)."""
        curve = self._curves.get(name)
        if curve:
            curve.setVisible(visible)

    def remove(self, name: str) -> None:
        """
        @brief Removes an indicator's curve and legend entry entirely.
        @details If it was a subplot-style indicator (e.g. RSI/MACD, not an
        overlay drawn on the main plot), also removes its dedicated subplot
        row and crosshair registration — otherwise the empty row/crosshair
        line pair is orphaned in the layout, which is what made repeated
        Load History/Start Stream clicks accumulate duplicate-looking panels.
        """
        curve = self._curves.pop(name, None)
        plot = self._plots.pop(name, None)
        self._legend_labels.pop(name, None)
        self._full_data.pop(name, None)
        if curve is None or plot is None:
            return
        plot.removeItem(curve)
        if plot.legend:
            plot.legend.removeItem(curve)
        if plot is not self._plot_layout.main_plot:
            self._on_remove_plot(plot)
            self._plot_layout.remove_subplot(plot)

    def clear(self) -> None:
        self._curves.clear()
        self._plots.clear()
        self._legend_labels.clear()
        self._full_data.clear()
        self._region_items.clear()
        self._script_info.clear()
        self._marker_layer.clear_all()

    # ------------------------------------------------------------------ #
    # BOT-032 — custom indicator script backgrounds & status panel
    # ------------------------------------------------------------------ #

    def set_script_regions(
        self, key: str, spans: list[tuple[float, float, str, float]]
    ) -> None:
        """
        @brief Draws (or extends) a script's background tint spans.
        @param spans (start_x, end_x, color, opacity) tuples, always the full
        current set — same "always the whole series" contract as
        update_data(). Existing spans are updated in place via setRegion()
        rather than being torn down and recreated, since the common case is
        one previous span growing by exactly one bar; only genuinely new spans
        allocate a new LinearRegionItem.
        @details Regions always draw on the main price plot regardless of the
        owning script's `overlay` flag — a background tint is a property of
        the whole timeline, not of one particular price/subplot scale.
        """
        items = self._region_items.setdefault(key, [])
        for index, (start, end, color, opacity) in enumerate(spans):
            if index < len(items):
                items[index].setRegion((start, end))
                continue
            region_item = pg.LinearRegionItem(
                values=(start, end),
                brush=pg.mkBrush(_color_with_alpha(color, opacity)),
                pen=pg.mkPen(None),
                movable=False,
            )
            region_item.setZValue(_REGION_Z_VALUE)
            self._plot_layout.main_plot.addItem(region_item)
            items.append(region_item)

    def clear_script_regions(self, key: str) -> None:
        """Removes every background span belonging to one script."""
        for item in self._region_items.pop(key, []):
            self._plot_layout.main_plot.removeItem(item)

    def set_script_info(self, key: str, fields: list[InfoField]) -> None:
        """
        @brief Replaces one script's status-panel rows and re-renders the
        shared panel label.
        @details All active scripts' rows are shown together (grouped by
        script) rather than each script getting its own label, so the panel
        doesn't grow a new widget per enabled script.
        """
        if fields:
            self._script_info[key] = fields
        else:
            self._script_info.pop(key, None)
        self._render_script_info_panel()

    def clear_script_info(self, key: str) -> None:
        self._script_info.pop(key, None)
        self._render_script_info_panel()

    def set_script_markers(self, key: str, markers: list[MarkerPoint]) -> None:
        """Draws (replacing) one script's Buy/Sell-style labelled markers."""
        self._marker_layer.set_markers(key, markers)

    def clear_script_markers(self, key: str) -> None:
        self._marker_layer.clear(key)

    def _render_script_info_panel(self) -> None:
        rows = [
            f"<span style='color:{field.color or _DEFAULT_INFO_COLOR}'>"
            f"{field.label}: {field.value}</span>"
            for fields in self._script_info.values()
            for field in fields
        ]
        self._plot_layout.script_info_label.setText("<br>".join(rows))


def _color_with_alpha(color: str, opacity: float) -> QtGui.QColor:
    """@brief Turns a plain hex color + a 0..1 opacity into a QColor with alpha.
    @details Kept separate from PlottedRegion itself, which deliberately has
    no QColor/UI-toolkit dependency (see the domain layer's guard test) —
    this is the one place that dependency is allowed to exist."""
    qcolor = pg.mkColor(color)
    qcolor.setAlphaF(max(0.0, min(1.0, opacity)))
    return qcolor
