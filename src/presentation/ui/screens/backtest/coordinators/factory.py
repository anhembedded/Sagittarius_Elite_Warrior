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
from ..logic.chart_canvas_view import ChartDisplayMode
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
    execution: ExecutionCoordinator


def build_coordinators(presenter) -> Coordinators:
    """Construct all six, in dependency order.

    The order matters in one place: `ChartRenderCoordinator` is handed
    `StrategyConfigCoordinator.refresh_market_rule_verification`, so that one
    must exist first.
    """
    # Reads `_all_trades` through a lambda rather than being handed the
    # list: the presenter rebinds it on every run, and three existing
    # tests assign `presenter._all_trades` directly before calling in.
    _trade_log = TradeLogCoordinator(
        view_model=presenter._view_model,
        get_all_trades=lambda: presenter._all_trades,
        set_chart_display_timezone=lambda tz: presenter.view.set_display_timezone(tz),
        ask_export_path=presenter._ask_trade_log_export_path,
        logger=presenter._logger,
    )
    _strategy_config = StrategyConfigCoordinator(
        view_model=presenter._view_model,
        strategy_registry=presenter._strategy_registry,
        logger=presenter._logger,
        get_strategy_params=lambda: presenter._strategy_params,
        set_strategy_params=presenter._set_strategy_params,
        get_symbol=lambda: presenter._symbol,
        # `lambda`, not `presenter._market_metadata_cache.get`: binding the
        # method captures the cache object that exists right now, and
        # tests replace `presenter._market_metadata_cache` after
        # construction. The bound version read the original cache and
        # reported UNVERIFIED_MISSING for every symbol.
        get_market_metadata=lambda symbol: presenter._market_metadata_cache.get(symbol),
        get_current_raw_klines=lambda: presenter._current_raw_klines,
        notify_config_changed=presenter._on_config_input_changed,
    )
    _indicators = IndicatorCoordinator(
        view_model=presenter._view_model,
        strategy_registry=presenter._strategy_registry,
        logger=presenter._logger,
        script_runner=presenter._chart_script_runner,
        get_first_chart_card=presenter._first_chart_card,
        get_active_strategy_lines=lambda: presenter._active_strategy_lines,
        get_current_raw_klines=lambda: presenter._current_raw_klines,
        get_chart_mode=lambda: getattr(
            presenter.view, "chart_mode", ChartDisplayMode.OHLC
        ),
        apply_after_native_fallback=presenter._apply_after_native_fallback,
        emit_strategy_line=presenter._chartStrategyLineSignal.emit,
        emit_strategy_region=presenter._chartStrategyRegionSignal.emit,
        set_chart_script_keys=presenter._set_chart_script_keys,
    )
    _data_sync = DataSyncCoordinator(
        dispatcher=presenter.dispatcher,
        get_symbol=lambda: presenter._symbol,
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
        view_model=presenter._view_model,
        dispatcher=presenter.dispatcher,
        thread_manager=presenter._thread_manager,
        logger_=presenter._logger,
        get_symbol=lambda: presenter._symbol,
        get_active_strategy_lines=lambda: presenter._active_strategy_lines,
        set_current_raw_klines=presenter._set_current_raw_klines,
        refresh_market_rule_verification=(
            # The local, not `presenter._strategy_config`: that attribute is
            # only assigned after this function returns, so reading it here
            # raised AttributeError for every test that built a presenter.
            _strategy_config.refresh_market_rule_verification
        ),
        log_dev_trace=presenter._log_dev_trace,
        format_coverage_message=DataSyncCoordinator.format_coverage_message,
        # Routed through the presenter's own methods, not bound straight
        # to the indicator coordinator: a test replaces
        # `presenter._on_ema_toggled` with a Mock and asserts the
        # mode-change path calls it. Binding early skipped it entirely.
        set_strategy_lines_visible=lambda visible: presenter._on_ema_toggled(visible),
        set_script_overlay_lines_visible=(
            lambda visible: presenter._set_script_overlay_lines_visible(visible)
        ),
        get_chart_klines_fetch_limit=lambda: presenter._chart_klines_fetch_limit,
        get_current_config=presenter._get_current_config,
        is_busy=presenter._is_busy_for_preview,
        next_preview_id=presenter._claim_preview_id,
        get_active_preview_id=lambda: presenter._active_preview_id,
        emit_preview_ready=presenter._previewDataReadySignal.emit,
        run_preview_worker=presenter._run_chart_preview,
    )
    _execution = ExecutionCoordinator(
        view_model=presenter._view_model,
        dispatcher=presenter.dispatcher,
        script_runner=presenter._chart_script_runner,
        get_symbol=lambda: presenter._symbol,
        get_chart_klines_fetch_limit=lambda: presenter._chart_klines_fetch_limit,
        get_chart_script_keys=lambda: presenter._chart_script_keys,
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
        execution=_execution,
    )
