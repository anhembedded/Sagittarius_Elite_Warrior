from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

from .candlestick_item import FastCandlestickItem
from .crosshair_controller import CrosshairController
from .indicator_manager import IndicatorManager
from .plot_layout import ChartPlotLayout


class ChartCard(BaseCard):
    """
    @brief The Chart component for visualizing Candlestick data & Extensible Technical Indicators.
    @details Facade Pattern — composes ChartPlotLayout, CrosshairController, IndicatorManager and
    FastCandlestickItem, and exposes one stable API surface to the Presenter. Each collaborator
    owns exactly one concern (layout, crosshair, indicators, rendering), keeping this class a
    thin orchestrator instead of a God Object.
    """

    def __init__(self, symbol: str, parent=None):
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol

        self.plot_layout = ChartPlotLayout()
        self.body_layout.addWidget(self.plot_layout.widget)

        self.candlestick = FastCandlestickItem()
        self.plot_layout.main_plot.addItem(self.candlestick)

        self.crosshair = CrosshairController(
            scene=self.plot_layout.widget.scene(),
            label=self.plot_layout.crosshair_label,
        )
        self.crosshair.register_plot(self.plot_layout.main_plot)

        self.indicators = IndicatorManager(
            plot_layout=self.plot_layout,
            on_new_plot=self.crosshair.register_plot,
        )

    # ==========================================
    # PUBLIC API FOR PRESENTER
    # ==========================================
    def set_symbol_title(self, symbol: str) -> None:
        self.symbol = symbol
        self.lbl_title.setText(f"Live Chart: {symbol}")

    def render_historical_data(
        self, data: list[tuple[float, float, float, float, float]]
    ) -> None:
        self.candlestick.generate_picture(data)
        self.plot_layout.main_plot.autoRange()

    def update_last_candle(
        self,
        timestamp: float,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> None:
        self.candlestick.update_live_candle(timestamp, open_p, high_p, low_p, close_p)

    def append_closed_candle(
        self,
        timestamp: float,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> None:
        self.candlestick.append_closed_candle(timestamp, open_p, high_p, low_p, close_p)

    def add_overlay_indicator(self, name: str, color: str) -> None:
        self.indicators.add_overlay(name, color)

    def add_subplot_indicator(
        self, name: str, color: str, height_ratio: int = 1
    ) -> None:
        self.indicators.add_subplot(name, color, height_ratio)

    def update_indicator_data(
        self, name: str, x_data: list[float], y_data: list[float]
    ) -> None:
        self.indicators.update_data(name, x_data, y_data)

    def _mouse_moved(self, evt) -> None:
        """Back-compat entry point (also used directly by tests); delegates to CrosshairController."""
        self.crosshair.handle_mouse_moved(evt)

    def cleanup(self) -> None:
        """
        @brief Garbage collection method. Strict cleanup of C++ bindings.
        """
        self.crosshair.dispose()
        self.indicators.clear()
        self.plot_layout.clear()
