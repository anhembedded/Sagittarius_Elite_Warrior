from typing import Callable

import pyqtgraph as pg

from .plot_layout import ChartPlotLayout


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
        curve = self._curves.get(name)
        if not curve:
            return
        curve.setData(x=x_data, y=y_data)
        if y_data:
            self._legend_labels[name].setText(f"{name}: {y_data[-1]:.4f}")

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
