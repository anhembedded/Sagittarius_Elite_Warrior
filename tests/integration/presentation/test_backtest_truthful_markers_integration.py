from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
    _LONG_ENTRY_LABEL,
    _LONG_EXIT_LABEL,
    trade_flag_markers,
)


@pytest.fixture
def sample_long_only_result() -> BacktestResult:
    trade = Trade(
        symbol="BTCUSDT",
        entry_time=datetime(2026, 8, 17, 4, 0, tzinfo=UTC),
        entry_price=60000.0,
        exit_time=datetime(2026, 8, 17, 8, 0, tzinfo=UTC),
        exit_price=62000.0,
        quantity=1.0,
        pnl=2000.0,
        pnl_percent=3.33,
        fees_paid=10.0,
        entry_reason="EMA Long Trend",
        exit_reason=ExitReason.STRATEGY_SIGNAL,
    )
    curve = [
        (datetime(2026, 8, 17, 4, 0, tzinfo=UTC), 10000.0),
        (datetime(2026, 8, 17, 8, 0, tzinfo=UTC), 12000.0),
    ]
    metrics = BacktestMetrics.compute([trade], curve, 10000.0)
    return BacktestResult(
        symbol="BTCUSDT",
        initial_balance=10000.0,
        final_balance=12000.0,
        trades=[trade],
        equity_curve=curve,
        metrics=metrics,
    )


def test_backtest_truthful_markers_integration(qtbot, sample_long_only_result) -> None:
    # 1. Arrange View & Presenter
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

    # 2. Seed backtest trades and refresh trade log
    presenter._all_trades = sample_long_only_result.trades
    presenter._refresh_trade_log()

    # 3. Assert chart markers: Long-only result has strictly LONG_ENTRY and LONG_EXIT
    markers = trade_flag_markers(sample_long_only_result)
    assert len(markers) == 2
    assert markers[0][2] == _LONG_ENTRY_LABEL  # "MUA (LONG)"
    assert markers[1][2] == _LONG_EXIT_LABEL  # "ĐÓNG LONG"

    # Must NOT contain ambiguous "SELL" or "SHORT"
    for _, _, label, _, _ in markers:
        assert label != "SELL"
        assert label != "BÁN (SHORT)"
        assert "SHORT" not in label

    # 4. Assert Trade Logs table in ViewModel
    rows = presenter._view_model.tradeLogRows
    assert len(rows) == 1
    assert "vị thế mua" in rows[0]["positionLabel"]
    assert "SHORT" not in rows[0]["positionLabel"]

    # 5. Filter tab "short" contains 0 items in long-only engine
    presenter._view_model.tradeLogFilter = "short"
    filtered_rows = presenter._view_model.tradeLogRows
    assert len(filtered_rows) == 0
