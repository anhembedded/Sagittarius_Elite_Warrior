"""Builds the six Backtest coordinators and wires them to the presenter.

Lifted out of `BackTestPresenter.__init__` (`EPIC-003E` follow-up), which was
329 lines with a third of that being this wiring.

Every callable here closes over `presenter` on purpose. The wiring has to
read presenter state *late*: `_all_trades` is rebound on every run,
`_market_metadata_cache` and `_on_ema_toggled` are replaced by tests after
construction, and capturing any of them at build time silently routes around
the replacement. That mistake was made three times during `EPIC-003E`, each
time caught only by an existing test.

A factory, not a coordinator: it holds nothing and is called once. The
coordinators it returns still take plain callables and never see the
presenter itself.
"""

from __future__ import annotations

from typing import NamedTuple

from ..logic.backtest_fsm_matrix import BacktestActionKind
from ..logic.presenter_screen_state import PresenterBackedScreenState
from .chart_feed_coordinator import ChartFeedCoordinator
from .chart_preview_coordinator import ChartPreviewCoordinator
from .chart_render_coordinator import ChartRenderCoordinator
from .data_sync_coordinator import DataSyncCoordinator
from .execution_coordinator import ExecutionCoordinator
from .indicator_coordinator import IndicatorCoordinator
from .strategy_config_coordinator import StrategyConfigCoordinator
from .trade_log_coordinator import TradeLogCoordinator


class Coordinators(NamedTuple):
    """What `build_coordinators` hands back, named rather than positional so a
    reordering cannot silently swap two of them."""

    trade_log: TradeLogCoordinator
    strategy_config: StrategyConfigCoordinator
    indicators: IndicatorCoordinator
    data_sync: DataSyncCoordinator
    chart_render: ChartRenderCoordinator
    chart_preview: ChartPreviewCoordinator
    chart_feed: ChartFeedCoordinator
    execution: ExecutionCoordinator


def build_coordinators(presenter) -> Coordinators:
    """Construct all six, in dependency order.

    The order matters in one place: `ChartRenderCoordinator` is handed
    `StrategyConfigCoordinator.refresh_market_rule_verification`, so that one
    must exist first.
    """
    # One `IBacktestScreenState` for all six (`EPIC-013C`), replacing the
    # seventeen getter/setter lambdas this function used to build. It reads
    # the presenter on every access for the same reason those lambdas did:
    # `_all_trades` is rebound on every run, and several tests assign
    # `presenter._all_trades` / `_strategy_params` / `_active_preview_id`
    # directly after construction.
    state = PresenterBackedScreenState(presenter)

    _trade_log = TradeLogCoordinator(
        view_model=presenter._view_model,
        state=state,
        set_chart_display_timezone=lambda tz: presenter.view.set_display_timezone(tz),
        ask_export_path=presenter._ask_trade_log_export_path,
        logger=presenter._logger,
    )
    _strategy_config = StrategyConfigCoordinator(
        view_model=presenter._view_model,
        state=state,
        strategy_registry=presenter._strategy_registry,
        logger=presenter._logger,
        # `lambda`, not `presenter._market_metadata_cache.get`: binding the
        # method captures the cache object that exists right now, and
        # tests replace `presenter._market_metadata_cache` after
        # construction. The bound version read the original cache and
        # reported UNVERIFIED_MISSING for every symbol.
        get_market_metadata=lambda symbol: presenter._market_metadata_cache.get(symbol),
        notify_config_changed=presenter._on_config_input_changed,
    )
    _indicators = IndicatorCoordinator(
        view_model=presenter._view_model,
        state=state,
        strategy_registry=presenter._strategy_registry,
        logger=presenter._logger,
        script_runner=presenter._chart_script_runner,
        get_first_chart_card=presenter._first_chart_card,
        # Straight attribute read, not `getattr(..., ChartDisplayMode.OHLC)`:
        # `IBacktestView` declares `chart_mode`, so the fallback could only
        # ever hide a View that fails the contract — and probing by string
        # is invisible to the contract test that would otherwise catch it.
        get_chart_mode=lambda: presenter.view.chart_mode,
        apply_after_native_fallback=presenter._apply_after_native_fallback,
        emit_strategy_line=presenter._chartStrategyLineSignal.emit,
        emit_strategy_region=presenter._chartStrategyRegionSignal.emit,
    )
    _data_sync = DataSyncCoordinator(
        dispatcher=presenter.dispatcher,
        state=state,
        effective_data_interval=presenter._effective_data_interval,
        resolve_action_id=lambda: presenter._current_action_id(BacktestActionKind.SYNC),
        log_dev_trace=presenter._log_dev_trace,
        emit_progress=presenter._syncProgressSignal.emit,
        emit_succeeded=presenter._syncSucceededSignal.emit,
        emit_failed=presenter._syncFailedSignal.emit,
        emit_cancelled=presenter._syncCancelledSignal.emit,
    )
    _chart_render = ChartRenderCoordinator(
        view=presenter.view,
        state=state,
        view_model=presenter._view_model,
        logger_=presenter._logger,
        refresh_market_rule_verification=(
            # The local, not `presenter._strategy_config`: that attribute is
            # only assigned after this function returns, so reading it here
            # raised AttributeError for every test that built a presenter.
            _strategy_config.refresh_market_rule_verification
        ),
        log_dev_trace=presenter._log_dev_trace,
        # Routed through the presenter's own methods, not bound straight
        # to the indicator coordinator: a test replaces
        # `presenter._on_ema_toggled` with a Mock and asserts the
        # mode-change path calls it. Binding early skipped it entirely.
        set_strategy_lines_visible=lambda visible: presenter._on_ema_toggled(visible),
        set_script_overlay_lines_visible=(
            lambda visible: presenter._set_script_overlay_lines_visible(visible)
        ),
    )
    _chart_preview = ChartPreviewCoordinator(
        view=presenter.view,
        state=state,
        view_model=presenter._view_model,
        dispatcher=presenter.dispatcher,
        thread_manager=presenter._thread_manager,
        log_dev_trace=presenter._log_dev_trace,
        format_coverage_message=DataSyncCoordinator.format_coverage_message,
        get_current_config=presenter._get_current_config,
        is_busy=presenter._is_busy_for_preview,
        next_preview_id=presenter._claim_preview_id,
        emit_preview_ready=presenter._previewDataReadySignal.emit,
        run_preview_worker=presenter._run_chart_preview,
    )
    _execution = ExecutionCoordinator(
        view_model=presenter._view_model,
        state=state,
        dispatcher=presenter.dispatcher,
        resolve_action_id=lambda: presenter._current_action_id(
            BacktestActionKind.BACKTEST
        ),
        log_dev_trace=presenter._log_dev_trace,
        probe_coverage=presenter._probe_data_coverage,
        emit_coverage_missing=presenter._backtestCoverageMissingSignal.emit,
        emit_coverage_ready=presenter._backtestCoverageReadySignal.emit,
        emit_progress=presenter._backtestProgressSignal.emit,
        emit_failed=presenter._backtestFailedSignal.emit,
        emit_cancelled=presenter._backtestCancelledSignal.emit,
        emit_empty=presenter._backtestEmptySignal.emit,
        emit_succeeded=presenter._backtestSucceededSignal.emit,
        # Through the presenter, not bound to `_chart_feed` directly: that
        # local exists by now, but binding it here would freeze the object
        # the run hands its result to, and this factory has already been
        # burned four times by capturing something a test replaces later.
        on_result_ready=lambda *a: presenter._chart_feed.fetch_and_emit_chart_data(*a),
    )
    _chart_feed = ChartFeedCoordinator(
        state=state,
        dispatcher=presenter.dispatcher,
        script_runner=presenter._chart_script_runner,
        log_dev_trace=presenter._log_dev_trace,
        emit_chart_data_ready=presenter._chartDataReadySignal.emit,
        # Through the presenter's own methods, not bound to the indicator
        # coordinator: tests replace these on the presenter.
        emit_strategy_indicator_lines=(
            lambda *a: presenter._emit_strategy_indicator_lines(*a)
        ),
        emit_strategy_trend_zones=lambda *a: presenter._emit_strategy_trend_zones(*a),
    )
    return Coordinators(
        trade_log=_trade_log,
        strategy_config=_strategy_config,
        indicators=_indicators,
        data_sync=_data_sync,
        chart_render=_chart_render,
        chart_preview=_chart_preview,
        chart_feed=_chart_feed,
        execution=_execution,
    )
