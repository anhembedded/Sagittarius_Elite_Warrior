from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.presentation.ui.components.base_card import BaseCard

from .candlestick_item import FastCandlestickItem
from .chart_toolbar import ChartToolbar
from .chart_type_renderer import CANDLESTICK, HEIKIN_ASHI, ChartTypeRenderer
from .crosshair_controller import CrosshairController
from .edge_scroll_detector import EdgeScrollDetector
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

    #: BOT-035 — the user panned within EdgeScrollDetector's threshold of the
    #: left edge of currently-loaded history. Carries `self.symbol` since the
    #: Presenter owns multiple cards and needs to know which one to fetch
    #: more history for.
    sig_near_left_edge = Signal(str)

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
        self._volume_plot = self.plot_layout.add_subplot(height_ratio=1)
        self._volume_plot.addItem(self.volume.graphics_item)
        self.crosshair.register_plot(self._volume_plot)

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

        self.edge_scroll_detector = EdgeScrollDetector(
            plot=self.plot_layout.main_plot,
            get_raw_history=lambda: self._raw_history,
            parent=self,
        )
        self.edge_scroll_detector.sig_near_left_edge.connect(
            lambda: self.sig_near_left_edge.emit(self.symbol)
        )

        # Keeps volume bars + indicator curves windowed to the visible X
        # range on every pan/zoom (same technique FastCandlestickItem uses
        # internally for its own paint() — see its docstring) — a shared,
        # one-time wire-up here covers every indicator added through
        # IndicatorManager automatically, current and future.
        self.plot_layout.main_plot.vb.sigXRangeChanged.connect(self._on_x_range_changed)

    def check_near_left_edge(self) -> None:
        """Manually trigger an edge check (used for re-evaluation after cooldown)."""
        self.edge_scroll_detector.check_edge()

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
        # autoRange() (the branch above) disables Y auto-range as a pyqtgraph
        # ViewBox.setRange(rect=...) side effect (setRange(disableAutoRange=True)
        # turns off auto-range for BOTH axes whenever a full rect, not just an
        # explicit xRange/yRange, is given). Once that has happened even once
        # for this plot — e.g. a small dataset (like the Equity curve, which
        # almost always has <=150 points) hit the branch above — every later
        # call into THIS setXRange-only branch leaves the Y-axis frozen at
        # whatever autoRange() last computed, because setXRange() never
        # touches Y. Re-enabling Y auto-range here makes it refit to
        # (data's), not the previous render's, values.
        self.plot_layout.main_plot.enableAutoRange(y=True)
        self.plot_layout.main_plot.setXRange(first_t, last_t, padding=0.02)

    def prepend_historical_data(self, candles: list[OhlcCandle]) -> None:
        """
        @brief BOT-035 — nối thêm nến CŨ HƠN vào đầu dữ liệu đang có, khi user
        kéo/scroll gần hết dữ liệu bên trái.
        @details Khác hẳn render_historical_data() (dùng cho lần tải đầu
        tiên, luôn reset zoom về mặc định và nhảy view tới nến mới nhất) —
        ở đây KHÔNG được đổi zoom/pan hiện tại của user, vì user đang chủ
        động nhìn đúng chỗ đó.
        @param candles Oldest-first; caller (DashboardPresenter, qua
        HistoryPaginationController) chịu trách nhiệm đảm bảo timestamp của
        mỗi candle < timestamp của nến cũ nhất đang có, để tránh trùng dữ
        liệu — phương thức này không tự lọc lại.
        """
        if not candles or not self._raw_history:
            return
        self._raw_history = candles + self._raw_history
        if self.chart_type_renderer.chart_type == CANDLESTICK:
            self.candlestick.generate_picture(self._raw_history)
        else:
            self._render_chart_type()
        self._sync_indicator_window()

    def prepend_historical_volume(self, data: list[tuple[float, float, bool]]) -> None:
        """@param data: list of (timestamp, volume, is_bullish), oldest-first,
        older than what's currently loaded — see prepend_historical_data()."""
        if not data:
            return
        self.volume.render_historical(data + self.volume.as_tuples())
        (min_x, max_x), _ = self.plot_layout.main_plot.vb.viewRange()
        self.volume.refresh_window(min_x, max_x)

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

    def set_volume_visible(self, visible: bool) -> None:
        """@brief Shows/hides the Volume subplot row (BOT-056 §2.2 — "đã có
        sẵn, chỉ expose control"). Data stays loaded; only the row's own
        visibility toggles, so re-showing it needs no re-fetch/re-render."""
        self._volume_plot.setVisible(visible)

    def set_max_visible_x_range(self, max_seconds: float) -> None:
        """Restricts how far the user can zoom out on the X axis."""
        self.plot_layout.main_plot.setLimits(maxXRange=max_seconds)

    def add_overlay_indicator(self, name: str, color: str) -> None:
        self.indicators.add_overlay(name, color)
        self._sync_indicator_window()

    def add_subplot_indicator(
        self, name: str, color: str, height_ratio: int = 1
    ) -> None:
        self.indicators.add_subplot(name, color, height_ratio)
        self._sync_indicator_window()

    def update_indicator_data(
        self, name: str, x_data: list[float], y_data: list[float]
    ) -> None:
        self.indicators.update_data(name, x_data, y_data)

    def set_indicator_visible(self, name: str, visible: bool) -> None:
        self.indicators.set_visible(name, visible)

    def remove_indicator(self, name: str) -> None:
        self.indicators.remove(name)

    # ------------------------------------------------------------------ #
    # BOT-032 — custom indicator script backgrounds & status panel
    # ------------------------------------------------------------------ #

    def set_script_regions(
        self, key: str, spans: list[tuple[float, float, str, float]]
    ) -> None:
        self.indicators.set_script_regions(key, spans)

    def clear_script_regions(self, key: str) -> None:
        self.indicators.clear_script_regions(key)

    def set_script_info(self, key: str, fields: list) -> None:
        self.indicators.set_script_info(key, fields)

    def clear_script_info(self, key: str) -> None:
        self.indicators.clear_script_info(key)

    def set_script_markers(self, key: str, markers: list) -> None:
        self.indicators.set_script_markers(key, markers)

    def clear_script_markers(self, key: str) -> None:
        self.indicators.clear_script_markers(key)

    def _mouse_moved(self, evt) -> None:
        """Back-compat entry point (also used directly by tests); delegates to CrosshairController."""
        self.crosshair.handle_mouse_moved(evt)

    def _on_x_range_changed(self, _viewbox, x_range: tuple[float, float]) -> None:
        """Fired by pyqtgraph on every pan/zoom — keeps volume + indicators
        windowed to what's actually visible (see IndicatorManager/VolumeItem
        docstrings)."""
        min_x, max_x = x_range
        self.volume.refresh_window(min_x, max_x)
        self.indicators.refresh_window(min_x, max_x)

    def _sync_indicator_window(self) -> None:
        """Applies the CURRENT view range to indicators immediately after one
        is added — otherwise a freshly-added indicator shows its full series
        unwindowed until the next pan/zoom fires sigXRangeChanged."""
        (min_x, max_x), _ = self.plot_layout.main_plot.vb.viewRange()
        self.indicators.refresh_window(min_x, max_x)

    def cleanup(self) -> None:
        """
        @brief Garbage collection method. Strict cleanup of C++ bindings.
        """
        self.zoom_controls.dispose()
        self.viewport.dispose()
        self.crosshair.dispose()
        self.indicators.clear()
        self.plot_layout.clear()
