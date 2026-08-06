import pyqtgraph as pg


class ChartPlotLayout:
    """
    @brief Owns the pyqtgraph GraphicsLayoutWidget and all row/stretch bookkeeping.
    @details Single Responsibility: plot construction & layout only — no candlestick data,
    no indicator state, no mouse/crosshair handling.
    """

    MAIN_PLOT_ROW = 1
    MAIN_PLOT_STRETCH = 3

    def __init__(self) -> None:
        pg.setConfigOptions(antialias=True)

        self.widget = pg.GraphicsLayoutWidget()
        self.widget.setBackground("default")

        self.crosshair_label = self.widget.addLabel(
            "<span style='color: #888888; font-size: 11px;'>Hover to see data</span>",
            row=0,
            col=0,
            justify="right",
        )

        date_axis = pg.DateAxisItem(orientation="bottom")
        self.main_plot = self.widget.addPlot(
            row=self.MAIN_PLOT_ROW, col=0, axisItems={"bottom": date_axis}
        )
        self.main_plot.showGrid(x=True, y=True, alpha=0.2)

        # Enable TradingView style: Scroll zooms X, Y auto-scales to visible X
        self.main_plot.setMouseEnabled(x=True, y=True)
        self.main_plot.vb.setAutoVisible(y=True)
        self.main_plot.vb.enableAutoRange(axis="y", enable=True)
        self.widget.ci.layout.setRowStretchFactor(
            self.MAIN_PLOT_ROW, self.MAIN_PLOT_STRETCH
        )

        self.sub_plots: list[pg.PlotItem] = []
        self.plots: list[pg.PlotItem] = [self.main_plot]
        self._next_row = self.MAIN_PLOT_ROW + 1

    def add_subplot(self, height_ratio: int = 1) -> pg.PlotItem:
        """Adds a new subplot row below existing plots, X-linked to the main plot."""
        sub_plot = self.widget.addPlot(row=self._next_row, col=0)
        sub_plot.showGrid(x=True, y=True, alpha=0.2)
        sub_plot.setXLink(self.main_plot)

        self.widget.ci.layout.setRowStretchFactor(self._next_row, height_ratio)

        self.sub_plots.append(sub_plot)
        self.plots.append(sub_plot)
        self._next_row += 1
        return sub_plot

    def clear(self) -> None:
        self.sub_plots.clear()
        self.plots.clear()
        self.widget.clear()
