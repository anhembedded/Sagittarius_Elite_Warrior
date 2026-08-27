"""Reference-script and strategy-indicator overlays on the Backtest chart."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.runner import (
    IndicatorScriptRunner,
    qualified_line_name,
)

from ..logic.chart_canvas_view import ChartDisplayMode
from ..logic.strategy_indicator_lines import (
    assign_strategy_line_colors,
    compute_strategy_indicator_lines,
)
from ..logic.strategy_trend_zones import compute_strategy_trend_zones
from ..ports.i_backtest_screen_state import IBacktestScreenState

#: Width for a strategy line the strategy itself does not specify.
_DEFAULT_STRATEGY_LINE_WIDTH = 2


class IndicatorCoordinator:
    """Draws two unrelated families of overlay onto the chart and keeps the
    bookkeeping for both straight:

    - **Reference scripts** the user picks in the indicator modal, drawn
      through `IndicatorScriptRunner`.
    - **Strategy indicators and trend zones**, replayed from a throwaway
      instance of whatever strategy the run used.

    Chart cards are fetched through `get_first_chart_card` rather than held:
    the host is rebuilt on every chart-mode change, and a held reference
    would be a `deleteLater()`'d C++ object — the exact shape of `BUG-013`.
    """

    def __init__(
        self,
        view_model,
        state: IBacktestScreenState,
        strategy_registry,
        logger,
        script_runner: IndicatorScriptRunner,
        get_first_chart_card: Callable[[], Any],
        get_chart_mode: Callable[[], ChartDisplayMode],
        apply_after_native_fallback: Callable[..., None],
        emit_strategy_line: Callable[..., None],
        emit_strategy_region: Callable[..., None],
    ) -> None:
        self._view_model = view_model
        self._state = state
        self._strategy_registry = strategy_registry
        self._logger = logger
        self._script_runner = script_runner
        self._get_first_chart_card = get_first_chart_card
        self._get_chart_mode = get_chart_mode
        self._apply_after_native_fallback = apply_after_native_fallback
        self._emit_strategy_line = emit_strategy_line
        self._emit_strategy_region = emit_strategy_region

    # ---------------------------------------------------------------- #
    # Reference-script drawing (one call per script output)
    # ---------------------------------------------------------------- #

    def on_script_line(self, name: str, x_data: list, y_data: list) -> None:
        """BOT-064: one call per user-picked reference script line, mirrors
        `DashboardPresenter._on_indicator_data` — pure delegate to
        `IndicatorScriptRunner.draw()`, which registers the overlay/subplot
        curve on first use and knows the script's own line color."""
        card = self._get_first_chart_card()
        if card is not None:
            self._script_runner.draw(card, name, x_data, y_data)

    def on_script_region(self, key: str, spans: list) -> None:
        self._draw_via_host(
            "script regions", spans, self._script_runner.draw_region, key
        )

    def on_script_info(self, key: str, fields: list) -> None:
        self._draw_via_host("script info", fields, self._script_runner.draw_info, key)

    def on_script_marker(self, key: str, markers: list) -> None:
        self._draw_via_host(
            "script markers", markers, self._script_runner.draw_markers, key
        )

    def _draw_via_host(self, label: str, items: list, draw, key: str) -> None:
        """The three region/info/marker handlers differed only in the label,
        the runner method and the list — one shape, three copies."""
        if self._get_first_chart_card() is None:
            return
        # `drawn_count` is keyword-only on the presenter's method; passing it
        # positionally raised TypeError inside the Qt event loop, where five
        # tests reported it only as "Exceptions caught in Qt event loop".
        self._apply_after_native_fallback(
            label,
            lambda host: draw(host, key, items),
            drawn_count=len(items),
        )

    # ---------------------------------------------------------------- #
    # Visibility and host-rebuild bookkeeping
    # ---------------------------------------------------------------- #

    def reset_bookkeeping_after_host_rebuild(self) -> None:
        """The chart host was just replaced from scratch — nothing on the new
        one knows about strategy/script indicator lines drawn on the old one,
        and neither caches the underlying x/y series to replay, so drop the
        stale bookkeeping rather than let it silently desync (BOT-098F6D bug,
        2026-08-18: real run-ui.ps1 session — indicator lines vanished after a
        chart-mode round-trip, then the next `set_indicator_visible()` call
        crashed and was swallowed silently by `safe_ui_action`). Re-running
        the backtest already redraws every line from scratch.

        Shared by every rebuild path, because skipping it is not merely a
        cosmetic gap: `IndicatorScriptRunner`'s `ResourceScope` still holds a
        dispose callback bound to the already-`deleteLater()`'d old host, and
        the *next* run's `clear_from_chart()` invokes it unconditionally,
        crashing with a real shiboken "C++ object already deleted"
        `RuntimeError` (BUG-013, 2026-08-19 — reachable only through the
        fallback path, since F6D's own fix covered only the mode-change one).
        """
        self._state.active_strategy_lines.clear()
        self._script_runner.reset_after_host_replaced()

    def set_strategy_lines_visible(self, visible: bool) -> None:
        card = self._get_first_chart_card()
        if card is None:
            return
        for name in self._state.active_strategy_lines:
            card.set_indicator_visible(name, visible)

    def set_script_overlay_lines_visible(self, visible: bool) -> None:
        """BOT-065: the reference-script counterpart to
        `set_strategy_lines_visible` — not the same checkbox (a script's line
        count isn't tied to "Chỉ báo Chiến lược" at all), but the same
        underlying problem: an overlay script left plotted through
        Equity-solo mode drags the shared main plot's auto-range onto price
        values, squashing the equity curve flat. Subplot scripts (RSI/MACD,
        `overlay=False`) don't share that plot, so they're excluded."""
        card = self._get_first_chart_card()
        if card is None:
            return
        for key, active in self._script_runner.active.items():
            if not active.overlay:
                continue
            for line_name in active.registered_lines:
                card.set_indicator_visible(qualified_line_name(key, line_name), visible)

    # ---------------------------------------------------------------- #
    # Adding/removing scripts without a rerun
    # ---------------------------------------------------------------- #

    def on_script_selection_changed(self) -> None:
        """BOT-095F: dynamically adds or removes reference indicator scripts
        from the chart when toggled in the indicator picker modal, without
        requiring a full backtest rerun."""
        enabled_keys = set(self._view_model.script_model.enabled_keys)
        scripts_str = ", ".join(sorted(enabled_keys)) if enabled_keys else "Không có"
        self._logger.info(f"Đã cập nhật chỉ báo tham chiếu: {scripts_str}")

        current_active_keys = set(self._script_runner.active.keys())
        disabled_keys = current_active_keys - enabled_keys
        newly_enabled_keys = enabled_keys - current_active_keys

        card = self._get_first_chart_card()

        for key in disabled_keys:
            if card is not None:
                self._script_runner.remove_script(key, card)
            else:
                self._script_runner.active.pop(key, None)

        raw_klines = self._state.current_raw_klines
        if raw_klines:
            is_price_scale = self._get_chart_mode() is not ChartDisplayMode.EQUITY
            for key in newly_enabled_keys:
                self._script_runner.add_script(key, raw_klines)
                if not is_price_scale:
                    active = self._script_runner.active.get(key)
                    if active and active.overlay and card is not None:
                        for line_name in active.registered_lines:
                            card.set_indicator_visible(
                                qualified_line_name(key, line_name), False
                            )

        self._state.chart_script_keys = sorted(enabled_keys)

    # ---------------------------------------------------------------- #
    # Strategy-declared overlays, replayed off the thread that ran them
    # ---------------------------------------------------------------- #

    def emit_strategy_indicator_lines(
        self, action_id: int, config, raw_klines: list
    ) -> None:
        """BOT-060: draws whatever indicators the backtested strategy itself
        declares (`build_indicators()`), instead of the fixed `ema_ribbon`
        script this used to hardcode — so the chart always matches what
        actually drove that run's Buy/Sell decisions.

        Builds a second, throwaway strategy instance (construct-and-discard,
        the pattern BOT-047's save-validation uses) purely to replay its
        indicators over the candles already fetched — entirely separate from
        the real `StrategyEngine` run, so `strategy_engine.py` stays
        untouched.
        """
        strategy = self._throwaway_strategy(config)
        if strategy is None:
            return
        lines = compute_strategy_indicator_lines(strategy, raw_klines)
        colors = assign_strategy_line_colors(
            list(lines.keys()), strategy.chart_line_colors()
        )
        widths = strategy.chart_line_widths()
        for name, (x_data, y_data) in lines.items():
            self._emit_strategy_line(
                action_id,
                name,
                colors[name],
                x_data,
                y_data,
                widths.get(name, _DEFAULT_STRATEGY_LINE_WIDTH),
            )

    def emit_strategy_trend_zones(
        self, action_id: int, config, raw_klines: list
    ) -> None:
        """BOT-113: draws the backtested strategy's own long-term-trend
        background shading (`classify_trend_zone()`), TradingView's
        `bgcolor()` pattern.

        A second, separate throwaway instance from
        `emit_strategy_indicator_lines` — that one's indicators are already
        fully replayed to the end of `raw_klines` by the time this runs, so
        reusing the instance would resume mid-warmup instead of starting
        fresh. A strategy that never overrides `classify_trend_zone()` (every
        strategy predating BOT-113) computes an empty span list: one no-op
        emit, no zones drawn.
        """
        strategy = self._throwaway_strategy(config)
        if strategy is None:
            return
        self._emit_strategy_region(
            action_id, compute_strategy_trend_zones(strategy, raw_klines)
        )

    def _throwaway_strategy(self, config):
        strategy_cls = self._strategy_registry.available().get(config.strategy_key)
        if strategy_cls is None:
            return None
        return strategy_cls(config.strategy_params)
