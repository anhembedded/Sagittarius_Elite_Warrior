from datetime import UTC, datetime
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
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


def test_view_model_timezone_properties_and_signals(qtbot) -> None:
    vm = BackTestViewModel()
    assert vm.displayTimezone == "UTC"
    assert vm.displayTimezoneLabel == "UTC"
    assert len(vm.displayTimezoneOptions) >= 3

    with qtbot.waitSignal(vm.displayTimezoneChanged):
        vm.setDisplayTimezone("Asia/Ho_Chi_Minh")

    assert vm.displayTimezone == "Asia/Ho_Chi_Minh"
    assert vm.displayTimezoneLabel == "Asia/Ho_Chi_Minh"

    with qtbot.waitSignal(vm.openTimezonePickerRequested):
        vm.requestOpenTimezonePicker()


def test_timezone_change_does_not_dirty_config_or_dispatch_job(qapp) -> None:
    view = MagicMock()
    container = MagicMock()

    strategy_registry = MagicMock()
    strategy_registry.available.return_value = {}
    config = MagicMock()
    config.get.return_value = None
    config.get_all.return_value = {}

    container.resolve.side_effect = lambda key: (
        strategy_registry
        if "StrategyRegistry" in str(key)
        else config
        if "IConfig" in str(key)
        else MagicMock()
    )

    presenter = BackTestPresenter(
        view=view,
        container=container,
    )

    initial_fsm_state = presenter.fsm.current_state

    # Populate dummy trades
    trade = _make_dummy_trade(4, 8)
    presenter._all_trades = [trade]
    presenter._refresh_trade_log()

    # Initial UTC check: 04:00 and 08:00
    rows = presenter._view_model.tradeLogRows
    assert len(rows) == 1
    assert rows[0]["entryTimeText"] == "2026-08-17 04:00"
    assert rows[0]["exitTimeText"] == "2026-08-17 08:00"

    # Change display timezone to Asia/Ho_Chi_Minh (+7h)
    presenter._view_model.setDisplayTimezone("Asia/Ho_Chi_Minh")

    # Assert view.set_display_timezone was called
    view.set_display_timezone.assert_called_with("Asia/Ho_Chi_Minh")

    # Assert Trade Logs table re-rendered to 11:00 and 15:00
    rows_vn = presenter._view_model.tradeLogRows
    assert len(rows_vn) == 1
    assert rows_vn[0]["entryTimeText"] == "2026-08-17 11:00"
    assert rows_vn[0]["exitTimeText"] == "2026-08-17 15:00"

    # Invariant: FSM state must NOT have transitioned to CONFIG_DIRTY or RUNNING
    assert presenter.fsm.current_state == initial_fsm_state
    assert not presenter._view_model.isConfigDirty
