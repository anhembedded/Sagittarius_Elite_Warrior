"""One toolbar preview, from request to what lands on the chart.

@details `EPIC-013D`, split out of `chart_render_coordinator.py`. The two
have different lifecycles, which is the test `architecture-rule.md` §5.5
asks: *does changing how the chart draws force you to read or edit how a
stale preview is discarded?* No. Rendering happens whenever data arrives;
a preview is a request that races other requests and can be thrown away.

Ten of the sixteen constructor parameters that file carried belonged only
to this half — a dependency set that large and that exclusive is a second
coordinator hiding inside the first (`architecture-rule.md` §1 "I").
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_backtest_range_coverage import (
    GetBacktestRangeCoverageQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)

from ..logic.backtest_fsm_matrix import BacktestExecutionMode
from ..logic.time_range_preset import TimeRangePreset
from ..ports.i_backtest_screen_state import IBacktestScreenState
from ..ports.i_backtest_view import IBacktestView

logger = logging.getLogger("App.BackTestPresenter")


class ChartPreviewCoordinator:
    """Owns the lifecycle of one toolbar preview: whether to start it, the
    background query, and whether its late result is still wanted.

    @details The generation id lives on the presenter, not here — four tests
    read or write `presenter._active_preview_id` directly — so this reads it
    through `IBacktestScreenState` and claims a new one through
    `next_preview_id`. Qt slots stay on the presenter too; they need the
    `QObject` and their `@Slot`/`@safe_ui_action` decorators, and delegate
    their bodies here.
    """

    def __init__(
        self,
        view: IBacktestView,
        state: IBacktestScreenState,
        view_model,
        dispatcher,
        thread_manager,
        log_dev_trace: Callable[..., None],
        format_coverage_message: Callable[[BacktestRangeCoverage], str],
        get_current_config: Callable[[], Any],
        is_busy: Callable[[], bool],
        next_preview_id: Callable[[], int],
        emit_preview_ready: Callable[..., None],
        run_preview_worker: Callable[..., None],
    ) -> None:
        self._view = view
        self._state = state
        self._view_model = view_model
        self._dispatcher = dispatcher
        self._thread_manager = thread_manager
        self._log_dev_trace = log_dev_trace
        self._format_coverage_message = format_coverage_message
        self._get_current_config = get_current_config
        self._is_busy = is_busy
        self._next_preview_id = next_preview_id
        self._emit_preview_ready = emit_preview_ready
        self._run_preview_worker = run_preview_worker

    def request_preview(self) -> None:
        """Probe and preview a toolbar range without blocking the Qt thread."""
        if self._is_busy():
            return
        config = self._get_current_config()
        if self._view_model.timeRangePreset == TimeRangePreset.CUSTOM.value:
            if config.start_time is None or config.end_time is None:
                return
            if config.start_time >= config.end_time:
                return
        if (
            config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK
            and config.start_time is None
        ):
            # Same hazard `TickModeRequiresBoundedRangeRule`
            # (logic/pre_backtest_assertions.py) already refuses on the Run
            # button: an unbounded start_time makes
            # GetBacktestRangeCoverageQuery's SQL scan every row ever synced
            # for this symbol/interval with no lower bound, and tick mode's
            # interval is fine-grained (BOT-075's 1s default) — a real
            # session got a ThreadPoolExecutor worker stuck in that scan for
            # ~19s, still running 2s after `App.stop()` had already logged
            # "App stopped.", blocking process exit. That rule only guards
            # the Run button; this fires automatically on every toolbar
            # change (including a transient state before the time-range
            # preset has resolved to a bounded value) and was never covered.
            return
        preview_id = self._next_preview_id()
        self._thread_manager.submit(self._run_preview_worker, config, preview_id)

    def run_preview(self, config, preview_id: int) -> None:
        """Background preview query; the generation id fences rapid toolbar
        changes."""
        now = datetime.now(UTC)
        symbol = self._state.symbol
        try:
            response = self._dispatcher.dispatch(
                GetHistoricalKlinesQuery,
                GetHistoricalKlinesQuery(
                    symbol=symbol,
                    interval=config.timeframe,
                    limit=self._state.chart_klines_fetch_limit,
                    start_time=config.start_time,
                    end_time=config.end_time or now,
                    order_by_desc=True,
                ),
            )
            raw_klines = list(reversed(list(getattr(response, "data", response) or [])))
            coverage_response = self._dispatcher.dispatch(
                GetBacktestRangeCoverageQuery,
                GetBacktestRangeCoverageQuery(
                    symbol=symbol,
                    interval=config.timeframe,
                    start_time=config.start_time,
                    end_time=config.end_time or now,
                    now=now,
                ),
            )
            # BUG-072 — same "tolerate a test double's `.data` envelope"
            # unwrap as `raw_klines` above. Without it, a test's mocked
            # dispatcher returning a plain response object (not a real
            # `BacktestRangeCoverage`) sailed straight into
            # `_previewDataReadySignal`'s loosely-typed `object` argument and
            # crashed the interpreter marshaling it across the worker/main
            # thread queue.
            coverage = getattr(coverage_response, "data", coverage_response)
            self._emit_preview_ready(
                preview_id,
                coverage,
                map_klines(raw_klines),
                map_volume(raw_klines),
                raw_klines,
            )
        except Exception as exc:
            logger.exception("Fetching Backtest chart preview failed")
            self._log_dev_trace("preview_query_failed", message=str(exc))

    def on_preview_data_ready(
        self,
        preview_id: int,
        coverage: BacktestRangeCoverage,
        klines: list,
        volume: list,
        raw_klines: list | None = None,
    ) -> None:
        if preview_id != self._state.active_preview_id:
            self._log_dev_trace("preview_ignored", preview_id=preview_id)
            return
        if raw_klines is not None:
            self._state.current_raw_klines = list(raw_klines)
        self._view_model.set_data_coverage(
            coverage.is_fully_covered,
            ""
            if coverage.is_fully_covered
            else self._format_coverage_message(coverage),
        )
        self._view_model.set_needs_data_sync(not coverage.is_fully_covered)
        self._view.on_preview_data_ready(klines, volume)
        self._view_model.set_chart_preview_mode(True)
