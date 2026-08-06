from typing import Callable

import pyqtgraph as pg

from .plot_layout import ChartPlotLayout


class IndicatorManager:
    """
    @brief Adds and updates overlay/subplot technical indicators (e.g. SMA, RSI, MACD).
    @details Single Responsibility: indicator curve lifecycle only. Depends on ChartPlotLayout
    (to place curves) and an injected callback (to keep new subplots crosshair-aware) rather
    than reaching into CrosshairController directly — Dependency Inversion.
    """

    def __init__(
        self,
        plot_layout: ChartPlotLayout,
        on_new_plot: Callable[[pg.PlotItem], None],
    ) -> None:
        self._plot_layout = plot_layout
        self._on_new_plot = on_new_plot
        self._curves: dict[str, pg.PlotDataItem] = {}

    def add_overlay(self, name: str, color: str) -> None:
        """Adds a line indicator on top of the main candlestick plot (e.g. SMA)."""
        curve = self._plot_layout.main_plot.plot(
            pen=pg.mkPen(color=color, width=2), name=name
        )
        self._curves[name] = curve

    def add_subplot(self, name: str, color: str, height_ratio: int = 1) -> None:
        """Adds a separate subplot below the main chart (e.g. RSI, MACD, Volume)."""
        sub_plot = self._plot_layout.add_subplot(height_ratio=height_ratio)
        curve = sub_plot.plot(pen=pg.mkPen(color=color, width=2), name=name)
        self._curves[name] = curve
        self._on_new_plot(sub_plot)

    def update_data(self, name: str, x_data: list[float], y_data: list[float]) -> None:
        """Updates the data arrays for a specific indicator."""
        curve = self._curves.get(name)
        if curve:
            curve.setData(x=x_data, y=y_data)

    def clear(self) -> None:
        self._curves.clear()
