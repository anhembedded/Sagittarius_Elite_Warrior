from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

from .candlestick_item import FastCandlestickItem
from .crosshair_controller import CrosshairController
from .indicator_manager import IndicatorManager
from .plot_layout import ChartPlotLayout
from .price_line import LastPriceLine
from .viewport_controller import ViewportController
from .volume_renderer import VolumeItem


class ChartCard(BaseCard):
    """
    @brief The Chart component for visualizing Candlestick data & Extensible Technical Indicators.
    @details Facade Pattern — composes ChartPlotLayout, CrosshairController, IndicatorManager,
    VolumeItem, LastPriceLine, ViewportController and FastCandlestickItem, and exposes one stable
    API surface to the Presenter. Each collaborator owns exactly one concern (layout, crosshair,
    indicators, volume, last-price, viewport-follow, rendering), keeping this class a thin
    orchestrator instead of a God Object.
    """

    def __init__(self, symbol: str, parent=None):
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol

        self.plot_layout = ChartPlotLayout()
        self.body_layout.addWidget(self.plot_layout.widget)

        self.candlestick = FastCandlestickItem()
        self.plot_layout.main_plot.addItem(self.candlestick)

        self.price_line = LastPriceLine(self.plot_layout.main_plot)

        self.crosshair = CrosshairController(
            scene=self.plot_layout.widget.scene(),
            label=self.plot_layout.crosshair_label,
            ohlc_lookup=self.candlestick.get_ohlc_at,
        )
        self.crosshair.register_plot(self.plot_layout.main_plot, is_primary=True)

        self.volume = VolumeItem()
        volume_plot = self.plot_layout.add_subplot(height_ratio=1)
        volume_plot.addItem(self.volume.graphics_item)
        self.crosshair.register_plot(volume_plot)

        self.indicators = IndicatorManager(
            plot_layout=self.plot_layout,
            on_new_plot=self.crosshair.register_plot,
        )

        self.viewport = ViewportController(
            plot=self.plot_layout.main_plot,
            canvas=self.plot_layout.widget,
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
        if data:
            last_t, open_p, _, _, close_p = data[-1]
            self.price_line.update_price(close_p, close_p >= open_p)
            self.viewport.notify_new_data(last_t)

    def update_last_candle(
        self,
        timestamp: float,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> None:
        self.candlestick.update_live_candle(timestamp, open_p, high_p, low_p, close_p)
        self.price_line.update_price(close_p, close_p >= open_p)
        self.viewport.notify_new_data(timestamp)

    def append_closed_candle(
        self,
        timestamp: float,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> None:
        self.candlestick.append_closed_candle(timestamp, open_p, high_p, low_p, close_p)
        self.price_line.update_price(close_p, close_p >= open_p)
        self.viewport.notify_new_data(timestamp)

    def render_historical_volume(self, data: list[tuple[float, float, bool]]) -> None:
        """@param data: list of (timestamp, volume, is_bullish)."""
        self.volume.render_historical(data)

    def update_last_volume(
        self, timestamp: float, volume: float, is_bullish: bool
    ) -> None:
        self.volume.update_live(timestamp, volume, is_bullish)

    def append_closed_volume(
        self, timestamp: float, volume: float, is_bullish: bool
    ) -> None:
        self.volume.append_closed(timestamp, volume, is_bullish)

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

    def set_indicator_visible(self, name: str, visible: bool) -> None:
        self.indicators.set_visible(name, visible)

    def remove_indicator(self, name: str) -> None:
        self.indicators.remove(name)

    def _mouse_moved(self, evt) -> None:
        """Back-compat entry point (also used directly by tests); delegates to CrosshairController."""
        self.crosshair.handle_mouse_moved(evt)

    def cleanup(self) -> None:
        """
        @brief Garbage collection method. Strict cleanup of C++ bindings.
        """
        self.viewport.dispose()
        self.crosshair.dispose()
        self.indicators.clear()
        self.plot_layout.clear()
