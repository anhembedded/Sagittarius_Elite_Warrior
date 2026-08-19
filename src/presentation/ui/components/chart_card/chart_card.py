import logging
from collections.abc import Sequence

import pyqtgraph as pg
from PySide6.QtCore import QPointF, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from Sagittarius_Elite_Warrior.src.presentation.ui.components.base_card import BaseCard

from .cached_frame_interaction import CachedFrameInteractionController
from .candlestick_item import FastCandlestickItem
from .chart_toolbar import ChartToolbar
from .chart_type_renderer import CANDLESTICK, HEIKIN_ASHI, ChartTypeRenderer
from .crosshair_controller import CrosshairController
from .edge_scroll_detector import EdgeScrollDetector
from .fps_overlay import ChartFpsOverlay
from .heikin_ashi import to_heikin_ashi
from .indicator_manager import IndicatorManager
from .plot_layout import ChartAntialiasMode, ChartPlotLayout
from .price_line import LastPriceLine
from .range_update_scheduler import RangeUpdateScheduler
from .viewport_controller import ViewportController
from .volume_renderer import VolumeItem
from .zoom_controls import ZoomControls

# Under "App" so StdLogger's handlers apply — see cached_frame_interaction.
logger = logging.getLogger("App.ChartCard")

OhlcCandle = tuple[float, float, float, float, float]

# Historical loads can bring in thousands of candles; showing all of them at
# once by default makes every subplot's auto-visible Y-range (Volume/RSI/
# MACD) span the ENTIRE history instead of a readable recent window.
_DEFAULT_INITIAL_VISIBLE_CANDLES = 150

#: Empty space allowed beyond the oldest/newest candle before the viewport is
#: clamped. Enough to keep the newest bar off the right edge, far too little to
#: reach a blank chart.
_VIEW_EDGE_MARGIN_BARS = 30

#: Used only when the loaded history is too short to infer bar spacing.
_FALLBACK_BAR_SECONDS = 60.0


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

    def __init__(
        self,
        symbol: str,
        parent=None,
        *,
        use_opengl: bool = False,
        antialias_mode: ChartAntialiasMode = ChartAntialiasMode.LAYERED,
        cached_interaction: bool = False,
        lod_enabled: bool = True,
    ):
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol
        self._use_opengl = bool(use_opengl)
        self._antialias_mode = antialias_mode
        self._cached_interaction_enabled = bool(cached_interaction)
        self._lod_enabled = bool(lod_enabled)
        self._raw_history: list[OhlcCandle] = []
        self._live_candle: OhlcCandle | None = None
        self._max_visible_seconds: float | None = None

        self._setup_layout()
        self._setup_components()
        self._connect_signals()
        self._log_environment()

    def _log_environment(self) -> None:
        """One-shot record of everything machine-specific about this chart.

        Rendering defects reproduce differently per machine (GPU vs software,
        DPI scaling, OpenGL fallback), so a bug report is only actionable if
        the log states which of those were actually in effect — not which
        were requested.
        """
        screen = self.screen() or QGuiApplication.primaryScreen()
        logger.info(
            "[chart-env] ChartCard(%s): render backend=%s (opengl requested=%s%s) "
            "| antialias=%s | LOD=%s | cached interaction=%s | DPR=%g | "
            "Qt platform=%s | screen=%s",
            self.symbol,
            self.plot_layout.render_backend,
            self._use_opengl,
            f", fallback: {self.plot_layout.backend_fallback_reason}"
            if self.plot_layout.backend_fallback_reason
            else "",
            self._antialias_mode.value,
            self._lod_enabled,
            self._cached_interaction_enabled,
            screen.devicePixelRatio() if screen else 0.0,
            QGuiApplication.platformName(),
            f"{screen.size().width()}x{screen.size().height()}" if screen else "?",
        )

    def _setup_layout(self) -> None:
        self.toolbar = ChartToolbar()
        self.add_to_header(self.toolbar)

        self.plot_layout = ChartPlotLayout(
            use_opengl=self._use_opengl,
            antialias_mode=self._antialias_mode,
        )
        self.body_layout.addWidget(self.plot_layout.widget)

    def _setup_components(self) -> None:
        self.candlestick = FastCandlestickItem(lod_enabled=self._lod_enabled)
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

        self.volume = VolumeItem(lod_enabled=self._lod_enabled)
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
        self.fps_overlay = ChartFpsOverlay(self.plot_layout.widget, parent=self)
        self.range_updates = RangeUpdateScheduler(self._apply_x_range, parent=self)
        self.cached_interaction: CachedFrameInteractionController | None = None
        self._create_cached_interaction()

    def _create_cached_interaction(self) -> None:
        if self.cached_interaction is not None:
            return
        if not self._cached_interaction_enabled:
            # Logged so a bug report can tell, without any interaction at all,
            # whether the preview overlay is even in play — a drag then pans
            # through pyqtgraph natively instead.
            logger.info(
                "[cached-frame] ChartCard(%s): cached interaction DISABLED — "
                "pan/zoom go straight to pyqtgraph",
                self.symbol,
            )
            return
        logger.info(
            "[cached-frame] ChartCard(%s): cached interaction ENABLED — "
            "pan/zoom inside the main plot preview through the overlay",
            self.symbol,
        )
        self.cached_interaction = CachedFrameInteractionController(
            canvas=self.plot_layout.widget,
            main_plot=self.plot_layout.main_plot,
            plots_provider=self._current_plots,
            on_before_frame_grab=self.range_updates.flush_pending,
            on_preview_started=self._suspend_crosshair_for_preview,
            on_preview_finished=self._restore_crosshair_after_preview,
            parent=self,
        )
        self.fps_overlay.add_paint_source(self.cached_interaction.preview_surface)

    def _current_plots(self) -> Sequence[pg.PlotItem]:
        """Live view of the main plot plus every subplot currently mounted."""
        return self.plot_layout.plots

    def _dispose_cached_interaction(self) -> None:
        if self.cached_interaction is None:
            return
        self.fps_overlay.remove_paint_source(self.cached_interaction.preview_surface)
        self.cached_interaction.dispose()
        self.cached_interaction = None

    def _suspend_crosshair_for_preview(self) -> None:
        self.crosshair.set_suspended(True)

    def _restore_crosshair_after_preview(self, viewport_position: QPointF) -> None:
        self.crosshair.set_suspended(False)
        scene_position = self.plot_layout.widget.mapToScene(viewport_position.toPoint())
        self.crosshair.handle_mouse_moved((scene_position,))

    def _connect_signals(self) -> None:
        self.edge_scroll_detector.sig_near_left_edge.connect(
            lambda: self.sig_near_left_edge.emit(self.symbol)
        )

        # Keeps volume bars + indicator curves windowed to the visible X
        # range on every pan/zoom (same technique FastCandlestickItem uses
        # internally for its own paint() — see its docstring) — a shared,
        # one-time wire-up here covers every indicator added through
        # IndicatorManager automatically, current and future.
        self.plot_layout.main_plot.vb.sigXRangeChanged.connect(self._on_x_range_changed)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.plot_layout.uses_opengl:
            # A QOpenGLWidget context only exists after native show. Hybrid
            # QQuickWidget composition can leave it None without raising;
            # validate before Backtest data/indicator curves arrive.
            QTimer.singleShot(0, self._validate_render_backend)

    def _validate_render_backend(self) -> None:
        if not self.plot_layout.uses_opengl:
            return
        viewport = self.plot_layout.widget.viewport()
        context_getter = getattr(viewport, "context", None)
        context = context_getter() if callable(context_getter) else None
        if context is not None and (
            not hasattr(context, "isValid") or context.isValid()
        ):
            return

        # setViewport() destroys the previous GL viewport. FPS instrumentation
        # owns an event filter + QLabel parented to that viewport, so dispose
        # it first and bind a fresh overlay to the CPU viewport afterwards.
        fps_was_enabled = self.fps_overlay.is_enabled
        self._dispose_cached_interaction()
        self.fps_overlay.dispose()
        self.plot_layout.validate_render_backend()
        self.fps_overlay = ChartFpsOverlay(self.plot_layout.widget, parent=self)
        self.fps_overlay.set_enabled(fps_was_enabled)
        self._create_cached_interaction()

    def check_near_left_edge(self) -> None:
        """Manually trigger an edge check (used for re-evaluation after cooldown)."""
        self.edge_scroll_detector.check_edge()

    # ==========================================
    # PUBLIC API FOR PRESENTER
    # ==========================================
    def set_symbol_title(self, symbol: str) -> None:
        self.symbol = symbol
        self.lbl_title.setText(f"Live Chart: {symbol}")

    def set_dev_mode(self, enabled: bool) -> None:
        """Shows chart paint FPS only for explicitly enabled developer sessions."""
        self.fps_overlay.set_enabled(enabled)

    def render_historical_data(self, data: list[OhlcCandle]) -> None:
        self._raw_history = list(data)
        self._live_candle = None
        if self.chart_type_renderer.chart_type == CANDLESTICK:
            self.candlestick.generate_picture(self._raw_history)
        else:
            self._render_chart_type()
        self._apply_view_bounds()
        self._set_initial_view_range(data)
        if data:
            last_t, open_p, _, _, close_p = data[-1]
            self.price_line.update_price(close_p, close_p >= open_p)
            self.viewport.notify_new_data(last_t)
        (min_x, max_x), _ = self.plot_layout.main_plot.vb.viewRange()
        logger.info(
            "[chart-data] ChartCard(%s): loaded %d candles spanning [%.1f, %.1f] "
            "| initial view x-range [%.1f, %.1f] | chart type=%s",
            self.symbol,
            len(self._raw_history),
            self._raw_history[0][0] if self._raw_history else 0.0,
            self._raw_history[-1][0] if self._raw_history else 0.0,
            min_x,
            max_x,
            self.chart_type_renderer.chart_type,
        )

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
        self._apply_view_bounds()
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
        candle = (timestamp, open_p, high_p, low_p, close_p)
        if self._raw_history and self._raw_history[-1][0] == timestamp:
            self._raw_history[-1] = candle
        else:
            self._raw_history.append(candle)
        self._live_candle = None
        if self.chart_type_renderer.chart_type == CANDLESTICK:
            self.candlestick.append_closed_candle(
                timestamp, open_p, high_p, low_p, close_p
            )
        else:
            self._render_chart_type()
        self.price_line.update_price(close_p, close_p >= open_p)
        self.viewport.notify_new_data(timestamp)

    def _log_chart_type(self, chart_type: str) -> None:
        """Logged separately from the data load because callers set the type
        *after* pushing data, so a type read during render_historical_data is
        always the previous one."""
        logger.info(
            "[chart-data] ChartCard(%s): chart type applied=%s",
            self.symbol,
            chart_type,
        )

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
        self._log_chart_type(chart_type)
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
        (min_x, max_x), _ = self.plot_layout.main_plot.vb.viewRange()
        self.volume.refresh_window(min_x, max_x)
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
        self._max_visible_seconds = max_seconds
        self._apply_view_bounds()

    def _apply_view_bounds(self) -> None:
        """Stops the viewport being dragged off the data into empty time.

        `maxXRange` alone caps how WIDE the view may get but says nothing
        about WHERE it may sit, so the user could pan arbitrarily far from
        the loaded candles and be left looking at a blank plot — observed in
        a real session as `0/5000 candles visible | view extends 1210361s
        BEFORE first candle`. Bounding xMin/xMax keeps at least part of the
        data reachable at all times.

        A margin of `_VIEW_EDGE_MARGIN_BARS` is deliberately allowed on each
        side: clamping to the data's exact extent would glue the newest
        candle to the right edge, and traders expect some breathing room
        ahead of it.
        """
        plot = self.plot_layout.main_plot
        if not self._raw_history:
            # No data yet: a bound here would fight `autoRange()` on first load.
            plot.setLimits(xMin=None, xMax=None, maxXRange=self._max_visible_seconds)
            return
        first_timestamp = self._raw_history[0][0]
        last_timestamp = self._raw_history[-1][0]
        margin = _VIEW_EDGE_MARGIN_BARS * self._bar_seconds()
        plot.setLimits(
            xMin=first_timestamp - margin,
            xMax=last_timestamp + margin,
            maxXRange=self._max_visible_seconds,
        )

    def _bar_seconds(self) -> float:
        """Spacing between candles, inferred from the loaded history."""
        if len(self._raw_history) < 2:
            return _FALLBACK_BAR_SECONDS
        span = self._raw_history[-1][0] - self._raw_history[0][0]
        spacing = span / (len(self._raw_history) - 1)
        return spacing if spacing > 0 else _FALLBACK_BAR_SECONDS

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
        if self._raw_history:
            self._sync_indicator_window()
        self.indicators.set_script_markers(key, markers)

    def clear_script_markers(self, key: str) -> None:
        self.indicators.clear_script_markers(key)

    def set_display_timezone(self, tz_name: str) -> None:
        """Sets the active display timezone for crosshair, tooltips and date axes."""
        self.crosshair.set_display_timezone(tz_name)
        self.plot_layout.set_display_timezone(tz_name)

    def _mouse_moved(self, evt) -> None:
        """Back-compat entry point (also used directly by tests); delegates to CrosshairController."""
        self.crosshair.handle_mouse_moved(evt)

    def _on_x_range_changed(self, _viewbox, x_range: tuple[float, float]) -> None:
        """Fired by pyqtgraph on every pan/zoom — keeps volume + indicators
        windowed to what's actually visible (see IndicatorManager/VolumeItem
        docstrings)."""
        min_x, max_x = x_range
        self.range_updates.schedule(min_x, max_x)

    def _apply_x_range(self, min_x: float, max_x: float) -> None:
        """Applies the final coalesced viewport to expensive renderers."""
        self.volume.refresh_window(min_x, max_x)
        self.indicators.refresh_window(min_x, max_x)
        self._log_applied_x_range(min_x, max_x)

    def _log_applied_x_range(self, min_x: float, max_x: float) -> None:
        """Records what the viewport actually shows after every real pan/zoom.

        DEBUG because it fires once per coalesced UI frame; `--dev` turns it
        on. This is the layer that reveals a viewport scrolled past the edge
        of the loaded candles — where markers and indicators still draw
        because their series are longer, so the chart looks like it "lost"
        its candles rather than like it ran out of price data.
        """
        if not logger.isEnabledFor(logging.DEBUG):
            return
        if not self._raw_history:
            logger.debug(
                "[chart-range] ChartCard(%s): x-range [%.1f, %.1f] | NO candle "
                "data loaded",
                self.symbol,
                min_x,
                max_x,
            )
            return
        first_t = self._raw_history[0][0]
        last_t = self._raw_history[-1][0]
        visible = sum(1 for candle in self._raw_history if min_x <= candle[0] <= max_x)
        uncovered_left = max(0.0, first_t - min_x)
        uncovered_right = max(0.0, max_x - last_t)
        logger.debug(
            "[chart-range] ChartCard(%s): x-range [%.1f, %.1f] | %d/%d candles "
            "visible | data [%.1f, %.1f] | view extends %.0fs BEFORE first "
            "candle and %.0fs AFTER last | type=%s%s",
            self.symbol,
            min_x,
            max_x,
            visible,
            len(self._raw_history),
            first_t,
            last_t,
            uncovered_left,
            uncovered_right,
            self.chart_type_renderer.chart_type,
            " <-- EMPTY REGION ON SCREEN, candles cannot be drawn there"
            if uncovered_left > 0 or uncovered_right > 0
            else "",
        )

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
        self._dispose_cached_interaction()
        self.zoom_controls.dispose()
        self.viewport.dispose()
        self.crosshair.dispose()
        self.fps_overlay.dispose()
        self.range_updates.dispose()
        self.indicators.clear()
        self.plot_layout.clear()
