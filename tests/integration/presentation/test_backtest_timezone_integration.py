from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)


@pytest.fixture
def dummy_trade() -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=datetime(2026, 8, 17, 3, 30, tzinfo=UTC),
        entry_price=50000.0,
        exit_time=datetime(2026, 8, 17, 7, 45, tzinfo=UTC),
        exit_price=52000.0,
        quantity=0.5,
        pnl=1000.0,
        pnl_percent=4.0,
        fees_paid=2.0,
        entry_reason="EMA Long",
        exit_reason=ExitReason.STRATEGY_SIGNAL,
    )


def test_backtest_timezone_integration_updates_trade_log_times(
    qtbot, dummy_trade
) -> None:
    # 1. Arrange View and Presenter
    view = BackTestView()
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

    # 2. Seed trade data
    presenter._all_trades = [dummy_trade]
    presenter._refresh_trade_log()

    # 3. Assert initial UTC state: entry at 03:30, exit at 07:45
    utc_rows = presenter._view_model.tradeLogRows
    assert len(utc_rows) == 1
    assert utc_rows[0]["entryTimeText"] == "2026-08-17 03:30"
    assert utc_rows[0]["exitTimeText"] == "2026-08-17 07:45"

    # 4. Action: User changes timezone to Asia/Ho_Chi_Minh (+7 hours)
    presenter._view_model.setDisplayTimezone("Asia/Ho_Chi_Minh")

    # 5. Assert: Table formatted times updated to 10:30 and 14:45
    vn_rows = presenter._view_model.tradeLogRows
    assert len(vn_rows) == 1
    assert vn_rows[0]["entryTimeText"] == "2026-08-17 10:30"
    assert vn_rows[0]["exitTimeText"] == "2026-08-17 14:45"

    # 6. Domain Data Truth Invariant: Raw Trade object entry/exit times remain UTC
    assert dummy_trade.entry_time.tzinfo == UTC
    assert dummy_trade.entry_time.hour == 3
    assert dummy_trade.exit_time.hour == 7

    # 7. Action: User switches to America/New_York (Summer EDT: UTC-4)
    presenter._view_model.setDisplayTimezone("America/New_York")
    ny_rows = presenter._view_model.tradeLogRows
    assert len(ny_rows) == 1
    assert ny_rows[0]["entryTimeText"] == "2026-08-16 23:30"
    assert ny_rows[0]["exitTimeText"] == "2026-08-17 03:45"

    # 8. Clean switch back to UTC
    presenter._view_model.setDisplayTimezone("UTC")
    restored_rows = presenter._view_model.tradeLogRows
    assert restored_rows[0]["entryTimeText"] == "2026-08-17 03:30"
    assert restored_rows[0]["exitTimeText"] == "2026-08-17 07:45"
