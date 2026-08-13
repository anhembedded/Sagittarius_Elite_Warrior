"""Tests for BacktestMetrics.compute (BOT-021) — known-scenario metric math."""

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _signal(action: SignalAction) -> Signal:
    return Signal(symbol="BTCUSDT", action=action, reason="test", price=100.0, time=_T0)


def _trade(pnl: float, fees: float = 0.0) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0,
        exit_price=100.0,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl / 10.0,
        fees_paid=fees,
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


# ================= BOT-079: Fee transparency & trade frequency =================


def test_total_fees_paid_sums_every_trades_fees():
    trades = [_trade(100.0, fees=1.0), _trade(-50.0, fees=2.0), _trade(30.0, fees=0.5)]

    metrics = BacktestMetrics.compute(trades, [], initial_balance=1000.0)

    assert metrics.total_fees_paid == 3.5


def test_avg_bars_per_trade_divides_equity_curve_length_by_trade_count():
    trades = [_trade(1.0) for _ in range(100)]
    equity_curve = [(_T0, 1000.0)] * 500  # 500 bars / 100 trades

    metrics = BacktestMetrics.compute(trades, equity_curve, initial_balance=1000.0)

    assert metrics.avg_bars_per_trade == 5.0


def test_high_fee_ratio_warning_triggers_when_fees_dominate_the_net_result():
    # Same shape as BUG-002: many small round trips, fees eating the result.
    trades = [_trade(-1.0, fees=10.0) for _ in range(50)]

    metrics = BacktestMetrics.compute(
        trades, [(_T0, 1000.0)] * 500, initial_balance=1000.0
    )

    assert metrics.has_high_fee_ratio is True


def test_high_fee_ratio_warning_does_not_trigger_for_a_healthy_strategy():
    trades = [_trade(100.0, fees=1.0), _trade(-20.0, fees=1.0)]

    metrics = BacktestMetrics.compute(trades, [], initial_balance=1000.0)

    assert metrics.has_high_fee_ratio is False


def test_high_trade_frequency_warning_triggers_when_bars_per_trade_is_low():
    trades = [_trade(1.0) for _ in range(100)]
    equity_curve = [(_T0, 1000.0)] * 500  # 5 bars/trade, below the threshold

    metrics = BacktestMetrics.compute(trades, equity_curve, initial_balance=1000.0)

    assert metrics.has_high_trade_frequency is True


def test_high_trade_frequency_warning_does_not_trigger_for_sparse_trades():
    trades = [_trade(1.0), _trade(1.0)]
    equity_curve = [(_T0, 1000.0)] * 1000  # 500 bars/trade

    metrics = BacktestMetrics.compute(trades, equity_curve, initial_balance=1000.0)

    assert metrics.has_high_trade_frequency is False


def test_no_warnings_and_zero_fee_fields_when_there_are_no_trades():
    metrics = BacktestMetrics.compute([], [(_T0, 1000.0)], initial_balance=1000.0)

    assert metrics.total_fees_paid == 0.0
    assert metrics.avg_bars_per_trade == 0.0
    assert metrics.has_high_fee_ratio is False
    assert metrics.has_high_trade_frequency is False


def test_reproduces_the_bug_002_scenario_fees_explain_almost_all_the_loss():
    """BOT-079: the real BUG-002 log reads "807 trades, net profit -80.71%"
    — read in isolation, that says "bad strategy". It doesn't: fee_percent
    charged both ways ate -80.11 of those points on its own. Reproduces the
    same shape through the real PaperExchange (flat price each round trip,
    so the strategy's own gross edge is exactly zero and every bit of loss
    is fees) rather than asserting hand-picked numbers."""
    exchange = PaperExchange(symbol="BTCUSDT", initial_balance=1000.0, fee_percent=0.1)
    for _ in range(807):
        exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T0)
        exchange.fill(_signal(SignalAction.SELL), price=100.0, time=_T0)

    equity_curve = [(_T0, 1000.0)] * 10_079

    metrics = BacktestMetrics.compute(
        exchange.trades, equity_curve, initial_balance=1000.0
    )

    assert metrics.total_closed_trades == 807
    assert metrics.net_profit < 0  # fees only, no gross edge either way
    # Fees explain almost all of the loss, not "a strategy with no edge".
    assert metrics.total_fees_paid >= abs(metrics.net_profit) * 0.9
    assert metrics.has_high_fee_ratio is True
    assert metrics.has_high_trade_frequency is True  # ~12.5 bars/trade
