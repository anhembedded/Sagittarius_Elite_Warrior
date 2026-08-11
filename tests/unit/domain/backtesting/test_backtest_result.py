"""Tests for BacktestResult.compute (BOT-021) — wiring, not metric math."""

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
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


def test_compute_wires_metrics_from_the_same_trades_and_equity_curve():
    trades = [_trade(100.0), _trade(-40.0)]
    equity_curve = [(_T0, 1000.0), (_T0, 1060.0)]

    result = BacktestResult.compute(
        symbol="BTCUSDT",
        initial_balance=1000.0,
        final_balance=1060.0,
        trades=trades,
        equity_curve=equity_curve,
    )

    assert result.symbol == "BTCUSDT"
    assert result.initial_balance == 1000.0
    assert result.final_balance == 1060.0
    assert result.trades == trades
    assert result.equity_curve == equity_curve
    assert result.metrics.total_closed_trades == 2
    assert result.metrics.net_profit == 60.0


def test_compute_copies_the_trades_and_equity_curve_lists():
    trades = [_trade(100.0)]
    equity_curve = [(_T0, 1000.0)]

    result = BacktestResult.compute(
        symbol="BTCUSDT",
        initial_balance=1000.0,
        final_balance=1100.0,
        trades=trades,
        equity_curve=equity_curve,
    )
    trades.append(_trade(-999.0))
    equity_curve.append((_T0, 0.0))

    assert len(result.trades) == 1
    assert len(result.equity_curve) == 1
