"""Getting finished-run data and strategy overlays onto the Backtest chart.

@details The toolbar preview used to live here too; `EPIC-012D` moved it to
`chart_preview_coordinator.py`. See that module for why.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..logic.chart_canvas_view import ChartDisplayMode
from ..ports.i_backtest_screen_state import IBacktestScreenState
from ..ports.i_backtest_view import IBacktestView

logger = logging.getLogger("App.BackTestPresenter")

#: Single fixed key for the strategy's own trend zones — unlike reference
#: scripts there is only ever one strategy per run.
_STRATEGY_TREND_ZONE_KEY = "strategy_trend_zone"


class ChartRenderCoordinator:
    """Owns what reaches the chart host: finished run data, strategy lines
    and trend zones, and chart-mode switches.

    Qt slots stay on the presenter — they need the `QObject` and their
    `@Slot`/`@safe_ui_action` decorators — and delegate their bodies here.
    """

    def __init__(
        self,
        view: IBacktestView,
        state: IBacktestScreenState,
        view_model,
        logger_,
        refresh_market_rule_verification: Callable[[], None],
        log_dev_trace: Callable[..., None],
        set_strategy_lines_visible: Callable[[bool], None],
        set_script_overlay_lines_visible: Callable[[bool], None],
    ) -> None:
        self._view = view
        self._state = state
        self._view_model = view_model
        self._logger = logger_
        self._refresh_market_rule_verification = refresh_market_rule_verification
        self._log_dev_trace = log_dev_trace
        self._set_strategy_lines_visible = set_strategy_lines_visible
        self._set_script_overlay_lines_visible = set_script_overlay_lines_visible

    def first_chart_card(self):
        """Never cached: the host is rebuilt on every chart-mode change, so a
        stored card becomes a `deleteLater()`'d C++ object (BUG-013)."""
        return self._view.chart_cards[0] if self._view.chart_cards else None

    # ---------------------------------------------------------------- #
    # Finished-run data
    # ---------------------------------------------------------------- #

    def on_data_ready(
        self, result, klines: list, volume: list, raw_klines: list | None = None
    ) -> None:
        if raw_klines is not None:
            self._state.current_raw_klines = list(raw_klines)
            self._refresh_market_rule_verification()
        self._log_dev_trace(
            "chart_data_ready",
            klines=len(klines),
            volume=len(volume),
            trades=len(result.trades),
        )
        self._logger.log_klines_loaded(len(klines), self._state.symbol)
        self._view.on_backtest_data_ready(result, klines, volume)
        # BUG-032: this is the one place a real BacktestResult chart lands —
        # clears the flag `on_preview_data_ready` set, so QML stops showing
        # the "preview" badge once real results are on screen.
        self._view_model.set_chart_preview_mode(False)

    def on_strategy_line(
        self, name: str, color: str, x_data: list, y_data: list, width: int = 2
    ) -> None:
        """BOT-060: one call per strategy indicator line, emitted once the
        whole run has been fed — adds the curve on first use, the way
        `IndicatorScriptRunner.draw()` does for Dev Board scripts, without
        needing that class at all (a strategy has no
        `.line_colors()`/`.compute()` to drive it). `width` (BOT-111) lets a
        strategy request a different weight per line."""
        card = self.first_chart_card()
        if card is None:
            return
        active = self._state.active_strategy_lines
        if name not in active:
            card.add_overlay_indicator(name, color, width)
            active.add(name)
        card.update_indicator_data(name, x_data, y_data)

    def on_strategy_region(self, spans: list) -> None:
        """BOT-113: the backtested strategy's own `classify_trend_zone()`
        output, emitted once per run under a fixed key — unlike a reference
        script's regions there is only ever one strategy per run, so no key
        travels through the signal."""
        if self.first_chart_card() is None:
            return
        self.apply_after_native_fallback(
            "strategy trend zones",
            lambda host: host.set_script_regions(_STRATEGY_TREND_ZONE_KEY, spans),
            drawn_count=len(spans),
        )

    def apply_after_native_fallback(
        self, feature_name: str, draw, *, drawn_count: int
    ) -> None:
        """Draw `draw` on the live host.

        Named for its now-deleted native-fallback history (BUG-038): a native
        C++/QML chart host used to raise `NativeUnsupportedFeatureError` for
        exactly this class of content (script regions/info/markers,
        equity/BOTH subplot) and this method rebuilt onto the Python host and
        replayed `draw`. The native host is gone outright — `draw` always
        succeeds on `PythonBacktestChartHost` — but every call site still
        routes through here rather than calling `draw(card)` directly, so the
        `[chart-region]` logging (`logging-rule.md` §2/§5: log what was
        applied, not just what was decided) stays in one place.
        """
        card = self.first_chart_card()
        if card is None:
            return
        draw(card)
        logger.debug(
            "[chart-region] %s: drew %d item(s) on %s",
            feature_name,
            drawn_count,
            type(card).__name__,
        )

    # ---------------------------------------------------------------- #
    # Chart mode
    # ---------------------------------------------------------------- #

    def on_mode_changed(self, mode_value: str) -> None:
        mode = ChartDisplayMode(mode_value)
        self._log_dev_trace("chart_mode_changed", mode=mode_value)
        self._view.set_chart_mode(mode)
        is_price_scale = mode is not ChartDisplayMode.EQUITY
        # Entry/exit PRICE markers AND the strategy indicator overlay are
        # both price-scale — meaningless, and for the overlay actively
        # harmful (drags the shared main plot's auto-range onto price
        # values), once the main plot shows Equity instead of price.
        controls = self._view.chart_controls
        controls.set_trade_flags_enabled(is_price_scale)
        controls.set_ema_enabled(is_price_scale)
        self._set_strategy_lines_visible(is_price_scale and controls.is_ema_checked())
        self._set_script_overlay_lines_visible(is_price_scale)
