from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.result_formatter import (
    format_result_summary,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)


def _make_result() -> BacktestResult:
    trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=110.0,
        quantity=1.0,
        pnl=10.0,
        pnl_percent=10.0,
        fees_paid=0.2,
    )
    metrics = BacktestMetrics(
        net_profit=10.0,
        net_profit_percent=1.0,
        gross_profit=10.0,
        gross_loss=0.0,
        max_drawdown_percent=0.5,
        total_closed_trades=1,
        percent_profitable=100.0,
        profit_factor=99.0,
        avg_trade=10.0,
        avg_winning_trade=10.0,
        avg_losing_trade=0.0,
        largest_winning_trade=10.0,
        largest_losing_trade=0.0,
    )
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1010.0,
        trades=[trade],
        equity_curve=[(_T0, 1000.0), (_T1, 1010.0)],
        metrics=metrics,
    )


def test_formats_every_field_from_the_real_domain_object_not_a_summary():
    text = format_result_summary(_make_result())

    assert "ETHUSDT" in text
    assert "1,000.00" in text  # initial_balance
    assert "1,010.00" in text  # final_balance
    assert "10.00" in text  # net_profit
    assert "+1.00%" in text  # net_profit_percent
    assert "0.50%" in text  # max_drawdown_percent
    assert "Closed trades: 1" in text
    assert "100.00%" in text  # percent_profitable
    assert "99.000" in text  # profit_factor
