"""Tests for BacktestMetrics.compute (BOT-021) — known-scenario metric math."""

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _trade(pnl: float) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0,
        exit_price=100.0,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl / 10.0,
        fees_paid=0.0,
    )


def test_compute_with_no_trades_returns_all_zero_metrics_but_still_computes_drawdown():
    equity_curve = [(_T0, 1000.0), (_T0, 900.0)]

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.total_closed_trades == 0
    assert metrics.net_profit == 0.0
    assert metrics.net_profit_percent == 0.0
    assert metrics.gross_profit == 0.0
    assert metrics.gross_loss == 0.0
    assert metrics.percent_profitable == 0.0
    assert metrics.profit_factor == 0.0
    assert metrics.avg_trade == 0.0
    assert metrics.max_drawdown_percent == 10.0  # (1000-900)/1000*100


def test_compute_known_scenario_matches_hand_calculated_metrics():
    # 3 trades: +100 (win), -50 (loss), +30 (win).
    trades = [_trade(100.0), _trade(-50.0), _trade(30.0)]
    # Equity peaks at 1200, drops to 1000 -> 16.6667% drawdown, the largest
    # peak-to-trough drop in the series (the later dip to 1080 is smaller).
    equity_curve = [
        (_T0, 1000.0),
        (_T0, 1200.0),
        (_T0, 1000.0),
        (_T0, 1080.0),
    ]

    metrics = BacktestMetrics.compute(trades, equity_curve, initial_balance=1000.0)

    assert metrics.gross_profit == 130.0
    assert metrics.gross_loss == -50.0
    assert metrics.net_profit == 80.0
    assert metrics.net_profit_percent == 8.0
    assert metrics.total_closed_trades == 3
    assert metrics.percent_profitable == (2 / 3) * 100
    assert metrics.profit_factor == 130.0 / 50.0
    assert metrics.avg_trade == 80.0 / 3
    assert metrics.avg_winning_trade == 65.0
    assert metrics.avg_losing_trade == -50.0
    assert metrics.largest_winning_trade == 100.0
    assert metrics.largest_losing_trade == -50.0
    assert abs(metrics.max_drawdown_percent - (200.0 / 1200.0 * 100)) < 1e-9


def test_breakeven_trades_count_toward_total_but_not_winners_or_losers():
    trades = [_trade(100.0), _trade(0.0)]

    metrics = BacktestMetrics.compute(trades, [], initial_balance=1000.0)

    assert metrics.total_closed_trades == 2
    assert metrics.percent_profitable == 50.0  # 1 winner / 2 total
    assert metrics.gross_profit == 100.0
    assert metrics.gross_loss == 0.0


def test_profit_factor_is_infinite_when_there_are_no_losing_trades():
    trades = [_trade(100.0), _trade(50.0)]

    metrics = BacktestMetrics.compute(trades, [], initial_balance=1000.0)

    assert metrics.profit_factor == float("inf")


def test_profit_factor_is_zero_when_there_are_no_winning_trades():
    trades = [_trade(-100.0), _trade(-50.0)]

    metrics = BacktestMetrics.compute(trades, [], initial_balance=1000.0)

    assert metrics.profit_factor == 0.0
