from typing import Callable

import pyqtgraph as pg

from .plot_layout import ChartPlotLayout
from .viewport_windowing import visible_slice_indices


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
