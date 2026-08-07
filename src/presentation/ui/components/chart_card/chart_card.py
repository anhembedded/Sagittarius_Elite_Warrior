from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

from .candlestick_item import FastCandlestickItem
from .chart_toolbar import ChartToolbar
from .chart_type_renderer import CANDLESTICK, HEIKIN_ASHI, ChartTypeRenderer
from .crosshair_controller import CrosshairController
from .heikin_ashi import to_heikin_ashi
from .indicator_manager import IndicatorManager
from .plot_layout import ChartPlotLayout
from .price_line import LastPriceLine
from .viewport_controller import ViewportController
from .volume_renderer import VolumeItem
from .zoom_controls import ZoomControls

OhlcCandle = tuple[float, float, float, float, float]

# Historical loads can bring in thousands of candles; showing all of them at
# once by default makes every subplot's auto-visible Y-range (Volume/RSI/
# MACD) span the ENTIRE history instead of a readable recent window.
_DEFAULT_INITIAL_VISIBLE_CANDLES = 150


class ChartCard(BaseCard):
    """
    @brief The Chart component for visualizing Candlestick data & Extensible Technical Indicators.
    @details Facade Pattern — composes ChartPlotLayout, CrosshairController, IndicatorManager,
    VolumeItem, LastPriceLine, ViewportController, ZoomControls, ChartTypeRenderer, ChartToolbar
    and FastCandlestickItem, and exposes one stable API surface to the Presenter. Each collaborator
    owns exactly one concern (layout, crosshair, indicators, volume, last-price, viewport-follow,
    zoom, chart-type rendering, timeframe UI), keeping this class a thin orchestrator instead of
    a God Object.
    """

    def __init__(self, symbol: str, parent=None):
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol
        self._raw_history: list[OhlcCandle] = []
        self._live_candle: OhlcCandle | None = None

        self.toolbar = ChartToolbar()
        self.add_to_header(self.toolbar)

        self.plot_layout = ChartPlotLayout()
        self.body_layout.addWidget(self.plot_layout.widget)

        self.candlestick = FastCandlestickItem()
        self.plot_layout.main_plot.addItem(self.candlestick)

        self.chart_type_renderer = ChartTypeRenderer(
            self.plot_layout.main_plot, self.candlestick
        )

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
            on_remove_plot=self.crosshair.unregister_plot,
        )

        self.viewport = ViewportController(
            plot=self.plot_layout.main_plot,
            canvas=self.plot_layout.widget,
        )

        self.zoom_controls = ZoomControls(
            plot=self.plot_layout.main_plot,
            canvas=self.plot_layout.widget,
        )

    # ==========================================
    # PUBLIC API FOR PRESENTER
    # ==========================================
    def set_symbol_title(self, symbol: str) -> None:
        self.symbol = symbol
        self.lbl_title.setText(f"Live Chart: {symbol}")

    def render_historical_data(self, data: list[OhlcCandle]) -> None:
        self._raw_history = list(data)
        self._live_candle = None
        if self.chart_type_renderer.chart_type == CANDLESTICK:
            self.candlestick.generate_picture(self._raw_history)
        else:
            self._render_chart_type()
        self._set_initial_view_range(data)
        if data:
            last_t, open_p, _, _, close_p = data[-1]
            self.price_line.update_price(close_p, close_p >= open_p)
            self.viewport.notify_new_data(last_t)

    def _set_initial_view_range(self, data: list[OhlcCandle]) -> None:
        """
        @brief Shows a recent, readable window by default instead of fitting
        the entire loaded history into view at once.
        @details Volume/RSI/MACD subplots auto-follow the main plot's visible
        X range (see ChartPlotLayout.add_subplot) — starting zoomed out to
        thousands of candles makes their Y-axis span the whole history too,
        so a handful of outliers (e.g. one huge volume spike) flatten
        everything else. A short recent window keeps them readable from the
        moment data loads, not just after the user manually zooms in.
        """
        if len(data) <= _DEFAULT_INITIAL_VISIBLE_CANDLES:
            self.plot_layout.main_plot.autoRange()
            return
        first_t = data[-_DEFAULT_INITIAL_VISIBLE_CANDLES][0]
        last_t = data[-1][0]
        self.plot_layout.main_plot.setXRange(first_t, last_t, padding=0.02)

    def update_last_candle(
        self,
        timestamp: float,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> None:
        self._live_candle = (timestamp, open_p, high_p, low_p, close_p)
        if self.chart_type_renderer.chart_type == CANDLESTICK:
            self.candlestick.update_live_candle(
                timestamp, open_p, high_p, low_p, close_p
            )
        else:
            self._render_chart_type()
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
        self._raw_history.append((timestamp, open_p, high_p, low_p, close_p))
        self._live_candle = None
        if self.chart_type_renderer.chart_type == CANDLESTICK:
            self.candlestick.append_closed_candle(
                timestamp, open_p, high_p, low_p, close_p
            )
        else:
            self._render_chart_type()
        self.price_line.update_price(close_p, close_p >= open_p)
        self.viewport.notify_new_data(timestamp)

    def set_chart_type(self, chart_type: str) -> None:
        """
        @brief Switches between "candlestick" / "line" / "area" / "heikin_ashi" rendering
        of the same underlying OHLC data — no re-fetch needed.
        @details Candlestick keeps its dedicated O(1) live-tick fast path; the other modes
        recompute from the retained history on every update (acceptable at typical kline
        tick rates — same O(N) tolerance already used elsewhere in this package, e.g.
        FastCandlestickItem.append_closed_candle).
        """
        self.chart_type_renderer.set_chart_type(chart_type)
        if chart_type == CANDLESTICK:
            # self.candlestick's last picture may hold transformed (e.g. Heikin Ashi)
            # data from a previous mode — rebuild it from the raw OHLC we retained.
            self.candlestick.generate_picture(self._raw_history)
            if self._live_candle:
                self.candlestick.update_live_candle(*self._live_candle)
        else:
            self._render_chart_type()

    def _render_chart_type(self) -> None:
        full_data = list(self._raw_history)
        if self._live_candle:
            full_data.append(self._live_candle)

        if self.chart_type_renderer.chart_type == HEIKIN_ASHI:
            self.candlestick.generate_picture(to_heikin_ashi(full_data))
        else:
            self.chart_type_renderer.render_line_data(full_data)

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
        self.zoom_controls.dispose()
        self.viewport.dispose()
        self.crosshair.dispose()
        self.indicators.clear()
        self.plot_layout.clear()
