from datetime import UTC, datetime
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_trade_logs_panel import (
    BackTestTradeLogsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.session_run_history import (
    make_run_snapshot,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.trade_table_model import (
    TradeTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
    StrategyChartOverlayService,
)


def _make_dummy_trade(
    entry_hour: int = 4, exit_hour: int = 8, pnl: float = 50.0
) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=datetime(2026, 8, 17, entry_hour, 0, tzinfo=UTC),
        entry_price=60000.0,
        exit_time=datetime(2026, 8, 17, exit_hour, 0, tzinfo=UTC),
        exit_price=61000.0,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=1.67,
        fees_paid=5.0,
        entry_reason="Signal",
        exit_reason=ExitReason.STRATEGY_SIGNAL,
    )


def _shown(panel: BackTestTradeLogsPanel, key: str) -> str:
    """What the Trades table shows in row 0's `key` column: the times are
    written in the display time zone as they paint (`EPIC-033L`)."""
    return panel.table.text(0, TradeTableModel.column(key))


def test_view_model_timezone_properties_and_signals(qtbot) -> None:
    vm = BackTestViewModel()
    assert vm.time_range.displayTimezone == "UTC"
    assert vm.time_range.displayTimezoneLabel == "UTC"
    assert len(vm.time_range.displayTimezoneOptions) >= 3

    with qtbot.waitSignal(vm.time_range.displayTimezoneChanged):
        vm.setDisplayTimezone("Asia/Ho_Chi_Minh")

    assert vm.time_range.displayTimezone == "Asia/Ho_Chi_Minh"
    assert vm.time_range.displayTimezoneLabel == "Asia/Ho_Chi_Minh"


def _build_presenter(view: MagicMock) -> BackTestPresenter:
    container = MagicMock()

    strategy_registry = MagicMock()
    strategy_registry.available.return_value = {}
    strategy_catalog = StrategyCatalogService(strategy_registry)
    chart_overlay = StrategyChartOverlayService(strategy_registry)
    config = MagicMock()
    config.get.return_value = None
    config.get_all.return_value = {}

    container.resolve.side_effect = lambda key: (
        strategy_registry
        if "StrategyRegistry" in str(key)
        else strategy_catalog
        if "IStrategyCatalog" in str(key)
        else chart_overlay
        if "IStrategyChartOverlay" in str(key)
        else config
        if "IConfig" in str(key)
        else InMemorySymbolMarketMetadataCache()
        if "ISymbolMarketMetadataCache" in str(key)
        else MagicMock()
    )

    presenter = BackTestPresenter(
        view=view,
        container=container,
    )
    return presenter


def test_timezone_change_does_not_dirty_config_or_dispatch_job(qapp) -> None:
    view = MagicMock()
    presenter = _build_presenter(view)

    initial_fsm_state = presenter.fsm.current_state

    # Populate dummy trades
    trade = _make_dummy_trade(4, 8)
    presenter._all_trades = [trade]
    presenter._refresh_trade_log()
    panel = BackTestTradeLogsPanel(presenter._view_model)

    # Initial UTC check: 04:00 and 08:00
    rows = presenter._view_model.trade_log.rows
    assert len(rows) == 1
    assert _shown(panel, "entry_time") == "2026-08-17 04:00:00"
    assert _shown(panel, "exit_time") == "2026-08-17 08:00:00"

    # The table writes times in the zone it reads as it paints, so a zone
    # change must make it paint again: the rows are replaced, which resets
    # the model (review of PR #356).
    resets = MagicMock()
    panel.table.model.modelReset.connect(resets)

    # Change display timezone to Asia/Ho_Chi_Minh (+7h)
    presenter._view_model.setDisplayTimezone("Asia/Ho_Chi_Minh")
    resets.assert_called_once()

    # Assert view.set_display_timezone was called
    view.set_display_timezone.assert_called_with("Asia/Ho_Chi_Minh")

    # Assert Trade Logs table re-rendered to 11:00 and 15:00
    rows_vn = presenter._view_model.trade_log.rows
    assert len(rows_vn) == 1
    assert _shown(panel, "entry_time") == "2026-08-17 11:00:00"
    assert _shown(panel, "exit_time") == "2026-08-17 15:00:00"

    # Invariant: FSM state must NOT have transitioned to CONFIG_DIRTY or RUNNING
    assert presenter.fsm.current_state == initial_fsm_state
    assert not presenter._view_model.isConfigDirty


_VIETNAM = "Asia/Ho_Chi_Minh"


def _ranged_config(start: datetime, end: datetime | None) -> BacktestRunConfig:
    return BacktestRunConfig(
        strategy_key="ema_crossover",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=10_000.0,
        start_time=start,
        end_time=end,
    )


def test_the_config_diff_follows_the_screens_display_time_zone(qapp) -> None:
    """`BOT-162`: the presenter hands the diff the zone the person chose (a dropped argument would
    revert it to UTC with every writer's own test still green)."""
    presenter = _build_presenter(MagicMock())
    presenter._view_model.setDisplayTimezone(_VIETNAM)
    presenter._last_run_config = _ranged_config(datetime(2026, 1, 1, tzinfo=UTC), None)
    presenter._get_current_config = lambda: _ranged_config(  # type: ignore[method-assign]
        datetime(2026, 1, 2, tzinfo=UTC), None
    )

    presenter._on_config_input_changed()

    assert presenter._view_model.configDiffSummary == (
        "Time range (2026-01-01 07:00:00..Now → 2026-01-02 07:00:00..Now) in "
        f"{_VIETNAM}"
    )


def test_the_no_data_message_follows_the_screens_display_time_zone(qapp) -> None:
    presenter = _build_presenter(MagicMock())
    presenter._view_model.setDisplayTimezone(_VIETNAM)
    presenter._is_current_pending_action = lambda *_a: True  # type: ignore[method-assign]
    presenter._finish_action = lambda *_a: None  # type: ignore[method-assign]
    coverage = MagicMock()
    coverage.missing_open_times = (datetime(2026, 8, 15, 9, 30, tzinfo=UTC),)

    presenter._on_backtest_coverage_missing_for_action(1, MagicMock(), coverage, False)

    assert presenter._view_model.run_result.dataCoverageMessage == (
        f"Missing candles from 2026-08-15 16:30:00 {_VIETNAM}."
    )


def test_the_run_history_rows_follow_the_screens_display_time_zone(qapp) -> None:
    presenter = _build_presenter(MagicMock())
    presenter._view_model.setDisplayTimezone(_VIETNAM)
    config = _ranged_config(datetime(2026, 1, 1, tzinfo=UTC), None)
    result = BacktestResult.compute(
        symbol=config.symbol,
        initial_balance=config.initial_balance,
        final_balance=config.initial_balance,
        trades=[],
        equity_curve=[],
    )
    presenter._run_history.push(
        make_run_snapshot(
            form_data={},
            run_config=config,
            result=result,
            klines=[],
            volume=[],
            now=datetime(2026, 1, 1, 15, 20, 5, tzinfo=UTC),
        )
    )

    presenter._refresh_session_run_history_view_model()

    [row] = presenter._view_model.sessionRunHistory
    assert row["label"].startswith(f"2026-01-01 22:20:05 {_VIETNAM} — ")


def test_the_coordinators_read_the_zone_from_the_screens_view_model(qapp) -> None:
    """`BOT-162`: the sync worker's provider and the chart preview's coverage message are wired
    to the same view model, and answer in the zone it holds now."""
    presenter = _build_presenter(MagicMock())
    coverage = MagicMock()
    coverage.missing_open_times = (datetime(2026, 8, 15, 9, 30, tzinfo=UTC),)

    assert presenter._data_sync._time_zone() == "UTC"
    presenter._view_model.setDisplayTimezone(_VIETNAM)

    assert presenter._data_sync._time_zone() == _VIETNAM
    assert presenter._chart_preview._format_coverage_message(coverage) == (
        f"Missing candles from 2026-08-15 16:30:00 {_VIETNAM}."
    )
