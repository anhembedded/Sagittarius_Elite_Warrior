"""Every `.connect()` the Backtest screen makes, in one place.

Lifted out of `BackTestPresenter` (`EPIC-003E` follow-up). Four methods, 42
`connect()` calls and no logic of their own: wiring is a job, not a
responsibility of the presenter, and keeping it here means a signal that
loses its handler shows up as a diff in one file.

Plain functions taking the presenter rather than a class: there is no state
to hold, and each is called exactly once (twice for the chart controls, which
are rebuilt with the chart host).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.health_feed import HealthFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.sync_progress_feed import (
    SyncProgressFeed,
)

from .backtest_state_fields import BACKTEST_STATE_FIELDS


def connect_ui_signals(presenter) -> None:
    presenter._view_model.runBacktestRequested.connect(presenter._on_run_backtest)
    presenter._view_model.cancelBacktestRequested.connect(presenter._on_cancel_backtest)
    presenter._view_model.syncRequested.connect(presenter._on_request_sync)
    presenter._view_model.selectedStrategyKeyChanged.connect(
        presenter._on_strategy_selection_changed
    )
    presenter._view_model.selectedTimeframeChanged.connect(
        presenter._on_timeframe_changed
    )
    presenter._view_model.selectedSymbolChanged.connect(
        presenter._on_symbol_selection_changed
    )
    presenter._view_model.openSymbolPickerRequested.connect(
        presenter._on_symbol_picker_open_requested
    )
    presenter._view_model.refreshSymbolOptionsRequested.connect(
        presenter._on_symbol_picker_refresh_requested
    )
    presenter._view_model.executionModeChanged.connect(
        presenter._on_execution_mode_changed
    )
    presenter._view_model.timeRangePresetChanged.connect(
        presenter._on_time_range_changed
    )
    presenter._view_model.displayTimezoneChanged.connect(
        presenter._on_display_timezone_changed
    )
    presenter._view_model.customStartTextChanged.connect(
        presenter._on_custom_time_changed
    )
    presenter._view_model.customEndTextChanged.connect(
        presenter._on_custom_time_changed
    )
    presenter._view_model.initialCapitalTextChanged.connect(
        presenter._on_capital_changed
    )
    presenter._view_model.capitalValidationRequested.connect(
        presenter._on_capital_validation_requested
    )
    presenter._view_model.selectedCurrencyChanged.connect(presenter._on_capital_changed)
    presenter._view_model.script_model.enabledKeysChanged.connect(
        presenter._on_indicator_script_selection_changed
    )
    presenter._view_model.botParamsSaveRequested.connect(
        presenter._on_bot_params_save_requested
    )
    presenter._view_model.strategyPropertiesSaveRequested.connect(
        presenter._on_strategy_properties_save_requested
    )
    presenter._view_model.strategyPropertiesCommitRequested.connect(
        presenter._on_strategy_properties_commit_requested
    )
    presenter._backtestSucceededSignal.connect(
        presenter._on_backtest_succeeded_for_action
    )
    presenter._backtestEmptySignal.connect(presenter._on_backtest_empty_for_action)
    presenter._backtestFailedSignal.connect(presenter._on_backtest_failed_for_action)
    presenter._backtestCancelledSignal.connect(
        presenter._on_backtest_cancelled_for_action
    )
    presenter._backtestProgressSignal.connect(
        presenter._on_backtest_progress_for_action
    )
    presenter._backtestCoverageMissingSignal.connect(
        presenter._on_backtest_coverage_missing_for_action
    )
    presenter._backtestCoverageReadySignal.connect(
        presenter._on_backtest_coverage_ready_for_action
    )
    presenter._chartDataReadySignal.connect(presenter._on_chart_data_ready_for_action)
    presenter._chartStrategyLineSignal.connect(
        presenter._on_chart_strategy_line_for_action
    )
    presenter._chartStrategyRegionSignal.connect(
        presenter._on_chart_strategy_region_for_action
    )
    presenter._chartScriptLineSignal.connect(presenter._on_chart_script_line)
    presenter._chartScriptRegionSignal.connect(presenter._on_chart_script_region)
    presenter._chartScriptInfoSignal.connect(presenter._on_chart_script_info)
    presenter._chartScriptMarkerSignal.connect(presenter._on_chart_script_marker)
    presenter._syncSucceededSignal.connect(presenter._on_sync_succeeded_for_action)
    presenter._syncFailedSignal.connect(presenter._on_sync_failed_for_action)
    presenter._syncCancelledSignal.connect(presenter._on_sync_cancelled_for_action)
    presenter._syncProgressSignal.connect(presenter._on_sync_progress_for_action)
    presenter._previewDataReadySignal.connect(presenter._on_preview_data_ready)
    presenter._uiLogSignal.connect(presenter._on_ui_log)
    presenter._symbolOptionsReadySignal.connect(presenter._on_symbol_options_ready)
    presenter._symbolOptionsFailedSignal.connect(presenter._on_symbol_options_failed)
    presenter._view_model.tradeLogQueryChanged.connect(
        presenter._on_trade_log_query_changed
    )
    presenter._view_model.tradeLogExportRequested.connect(
        presenter._on_trade_log_export_requested
    )


def connect_engine_events(presenter) -> None:
    """Subscribe to Engine EventBus events emitted from background handlers (Observer Pattern)."""
    presenter.event_bus.on(
        BacktestCompletedEvent, presenter._handle_backtest_completed_event
    )
    presenter.event_bus.on(BacktestFailedEvent, presenter._handle_backtest_failed_event)
    presenter.event_bus.on(
        SignalGeneratedEvent, presenter._handle_signal_generated_event
    )
    # Tiến độ đồng bộ là sự thật của HỆ THỐNG (Data Management cũng cần) →
    # đi qua SyncProgressFeed. Phần `action_id` bên dưới là sự thật RIÊNG
    # của màn này nên ở lại đây (`architecture-rule.md` §6).
    presenter._sync_feed = SyncProgressFeed(presenter.event_bus, parent=presenter)
    presenter._sync_feed.progressUpdated.connect(presenter._on_sync_progress)
    # Sức khoẻ hệ thống là sự thật của HỆ THỐNG, không riêng màn này — đi
    # qua HealthFeed, một nơi nghe nhiều màn hiển thị
    # (`architecture-rule.md` §6). Bản tự ghép chuỗi cũ ở đây từng **bỏ sót
    # `Container`** so với Dashboard, đúng hệ quả của việc mỗi màn tự chuẩn hoá.
    presenter._health_feed = HealthFeed(presenter.event_bus, parent=presenter)
    presenter._health_feed.healthUpdated.connect(presenter._on_health_report)


def connect_chart_controls(presenter) -> None:
    """`BacktestChartControls` (native, owned by `BackTestView`) only
    emits signals — same split as the QML ViewModel — so the actual
    chart-mutation logic (which needs `presenter._active_strategy_lines`'s
    state) lives here, not in the View."""
    controls = presenter.view.chart_controls
    if controls is None:
        return
    controls.sig_mode_changed.connect(presenter._on_chart_mode_changed)
    controls.sig_ema_toggled.connect(presenter._on_ema_toggled)
    controls.sig_volume_toggled.connect(presenter.view.set_volume_visible)
    controls.sig_trade_flags_toggled.connect(presenter.view.set_trade_flags_visible)

    chart_cards = presenter.view.chart_cards
    if chart_cards:
        chart_cards[0].connect_timeframe_changed(
            presenter._on_chart_toolbar_timeframe_selected
        )
        presenter._sync_chart_toolbar_timeframe()


def connect_state_tracking(presenter) -> None:
    """Marks the slice dirty whenever any remembered field changes.

    @details Derived from the same declaration `capture_state()` reads
    rather than nineteen hand-written `connect` lines: Qt's own convention
    names a property's notifier `<prop>Changed`, which every field here
    follows. A missing one raises instead of silently dropping that field
    out of the debounce.
    """
    if presenter._state_coordinator is None:
        return
    presenter._view_model.script_model.enabledKeysChanged.connect(
        presenter._mark_state_dirty
    )
    for field in BACKTEST_STATE_FIELDS:
        signal = getattr(presenter._view_model, f"{field.prop}Changed", None)
        if signal is None:
            raise AttributeError(
                f"{type(presenter._view_model).__name__} has no "
                f"{field.prop}Changed signal; EPIC-010F cannot track "
                f"{field.key!r} for persistence"
            )
        signal.connect(presenter._mark_state_dirty)
