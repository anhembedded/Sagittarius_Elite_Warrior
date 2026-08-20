"""Tests for BacktestMetrics.compute (BOT-021) — known-scenario metric math."""

import math
from datetime import UTC, datetime, timedelta

import pytest

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


# ---------------------------------------------------------------------------
# BOT-106A — Sharpe/Sortino/Calmar/Max Drawdown Duration/Consecutive streaks.
# ---------------------------------------------------------------------------


def _daily_curve(equity_values: list[float]) -> list[tuple[datetime, float]]:
    return [(_T0 + timedelta(days=i), v) for i, v in enumerate(equity_values)]


def test_sharpe_and_sortino_are_zero_not_a_float_precision_artifact_when_returns_are_constant():
    # Every bar compounds by the exact same 1% — mathematically zero
    # volatility, but statistics.stdev() over these floats lands on the
    # order of 1e-16, not exactly 0.0 (verified by actually running this
    # exact case before adding the math.isclose() guard: it produced a
    # Sharpe of ~3.2e15 instead of 0.0 — a real bug, not a hand-guess).
    equity_curve = _daily_curve([1000.0, 1010.0, 1020.1, 1030.301])

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.sharpe_ratio == 0.0
    assert metrics.sortino_ratio == 0.0


def test_sortino_is_zero_with_no_negative_bars_while_sharpe_still_reflects_volatility():
    # All 3 per-bar returns are positive but unequal (real volatility) —
    # Sortino has nothing to measure (no downside bars) and must read 0.0,
    # while Sharpe (which uses total volatility) must not.
    equity_curve = _daily_curve([1000.0, 1010.0, 1050.0, 1055.0])

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.sortino_ratio == 0.0
    assert metrics.sharpe_ratio == pytest.approx(18.43457869358698, rel=1e-9)


def test_sharpe_and_sortino_are_zero_with_fewer_than_2_bar_returns():
    assert (
        BacktestMetrics.compute(
            [], [(_T0, 1000.0)], initial_balance=1000.0
        ).sharpe_ratio
        == 0.0
    )
    assert BacktestMetrics.compute([], [], initial_balance=1000.0).sortino_ratio == 0.0


def test_max_drawdown_duration_bars_counts_bars_strictly_below_the_running_peak():
    # Peak 1000 at bar[0]; bar[1]/bar[2] sit below it (2-bar drawdown);
    # bar[3] recovers back to the peak (resets to 0); bar[4] sets a new
    # peak. Longest stretch strictly below a peak is 2 bars, not 4.
    equity_curve = _daily_curve([1000.0, 900.0, 950.0, 1000.0, 1050.0])

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.max_drawdown_duration_bars == 2


def test_max_drawdown_duration_bars_counts_through_the_end_when_never_recovered():
    equity_curve = _daily_curve([1000.0, 900.0, 850.0, 875.0])

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.max_drawdown_duration_bars == 3


def test_calmar_ratio_matches_hand_calculated_cagr_over_max_drawdown():
    # Exactly 1 year (365.25 days) start-to-end: 1000 -> dip to 900 (10%
    # drawdown, the only drawdown in the series) -> 1200 (CAGR = +20%
    # over exactly 1 year). Calmar = 20 / 10 = 2.0 exactly.
    equity_curve = [
        (_T0, 1000.0),
        (_T0 + timedelta(days=182.625), 900.0),
        (_T0 + timedelta(days=365.25), 1200.0),
    ]

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.max_drawdown_percent == 10.0
    assert metrics.calmar_ratio == pytest.approx(2.0, rel=1e-9)


def test_calmar_ratio_is_zero_with_no_real_drawdown_to_divide_by():
    equity_curve = _daily_curve([1000.0, 1050.0, 1100.0])  # monotonic, no dip

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.max_drawdown_percent == 0.0
    assert metrics.calmar_ratio == 0.0


def test_max_consecutive_wins_and_losses_track_separate_streaks_and_reset_on_breakeven():
    trades = [
        _trade(10.0),  # win streak 1
        _trade(-5.0),  # loss streak 1
        _trade(20.0),  # win streak 1
        _trade(30.0),  # win streak 2 <- longest win streak
        _trade(-1.0),  # loss streak 1
        _trade(-2.0),  # loss streak 2
        _trade(-3.0),  # loss streak 3 <- longest loss streak
        _trade(15.0),  # win streak 1
        _trade(0.0),  # breakeven — ends both streaks
        _trade(5.0),  # win streak 1 (restarted after the breakeven)
        _trade(5.0),  # win streak 2
    ]

    metrics = BacktestMetrics.compute(
        trades, [(_T0, 1000.0)] * len(trades), initial_balance=1000.0
    )

    assert metrics.max_consecutive_wins == 2
    assert metrics.max_consecutive_losses == 3


def test_no_trades_still_computes_equity_curve_driven_metrics_not_hardcoded_zero():
    # BOT-106A: Sharpe/Sortino/Calmar/max-drawdown-duration are driven by
    # the equity curve, not by trades — a strategy that opened zero trades
    # but held cash through a real drawdown-and-recover still gets a real
    # (non-fake-zero) reading for these, same as max_drawdown_percent
    # already did before this task.
    equity_curve = _daily_curve([1000.0, 900.0, 950.0, 1000.0, 1050.0])

    metrics = BacktestMetrics.compute([], equity_curve, initial_balance=1000.0)

    assert metrics.max_drawdown_duration_bars == 2
    assert metrics.max_consecutive_wins == 0
    assert metrics.max_consecutive_losses == 0


@pytest.mark.parametrize(
    "trades,equity_curve",
    [
        ([], []),
        ([], [(_T0, 1000.0)]),
        ([_trade(10.0)], [(_T0, 1000.0), (_T0, 1000.0)]),
        ([_trade(0.0)], [(_T0, 0.0), (_T0, 0.0)]),
    ],
)
def test_new_metrics_are_never_nan_or_infinite_for_degenerate_inputs(
    trades, equity_curve
):
    # BOT-106A acceptance criterion: safe when sigma == 0, never divides by
    # zero into NaN/Inf.
    metrics = BacktestMetrics.compute(trades, equity_curve, initial_balance=1000.0)

    for value in (
        metrics.sharpe_ratio,
        metrics.sortino_ratio,
        metrics.calmar_ratio,
    ):
        assert math.isfinite(value)
