"""Tests for `contracts/monte_carlo_simulation.py` (`BOT-107B`)."""

from __future__ import annotations

from datetime import UTC, datetime
from random import Random

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monte_carlo_simulation import (
    run_monte_carlo_simulation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade

_T0 = datetime(2024, 1, 1, tzinfo=UTC)
_INITIAL_BALANCE = 1000.0


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


class _AlternatingOrderRng(Random):
    """A real `random.Random` subclass (never a hand-shaped mock — this
    codebase's own `testing-rule.md` §2 rule) whose `shuffle()` alternates
    deterministically between two fixed orderings, so a 2-trade Monte Carlo
    run's per-path statistics are exact numbers to assert on rather than a
    statistical band."""

    def __init__(self, first_order: list[float], second_order: list[float]) -> None:
        super().__init__()
        self._orders = (list(first_order), list(second_order))
        self._next_index = 0

    def shuffle(self, x, random=None):
        x[:] = self._orders[self._next_index % 2]
        self._next_index += 1


# ---------------------------------------------------------------------------
# Guard clauses
# ---------------------------------------------------------------------------


def test_no_trades_raises_rather_than_fabricating_a_result():
    with pytest.raises(ValueError, match="at least one closed trade"):
        run_monte_carlo_simulation(
            [],
            _INITIAL_BALANCE,
            iterations=100,
            rng=Random(1),  # noqa: S311 — determinism, not cryptography
        )


def test_zero_iterations_raises_rather_than_fabricating_a_result():
    with pytest.raises(ValueError, match="at least one iteration"):
        run_monte_carlo_simulation(
            [_trade(10.0)],
            _INITIAL_BALANCE,
            iterations=0,
            rng=Random(1),  # noqa: S311 — determinism, not cryptography
        )


# ---------------------------------------------------------------------------
# Reshuffling is order-invariant for the total return, order-DEPENDENT for
# the path (drawdown, risk of ruin) — the two distinct questions this
# module exists to answer.
# ---------------------------------------------------------------------------


def test_median_return_is_the_same_regardless_of_shuffle_order():
    """Summing the same PnLs in any order gives the same total — a
    regression that started compounding order-dependently (e.g. via
    `pnl_percent` applied multiplicatively) would change this number."""
    trades = [_trade(-600.0), _trade(500.0)]

    result = run_monte_carlo_simulation(
        trades,
        _INITIAL_BALANCE,
        iterations=200,
        rng=Random(42),  # noqa: S311 — determinism, not cryptography
    )

    expected_return = (-600.0 + 500.0) / _INITIAL_BALANCE * 100
    assert result.median_return_percent == pytest.approx(expected_return)


def test_risk_of_ruin_and_max_drawdown_answer_different_questions():
    """Order [big loss, big win]: balance dips to 400 (40% of initial —
    triggers the 50%-of-initial Risk-of-Ruin threshold) then recovers to
    900, for a 60% peak-to-trough drawdown. Order [big win, big loss]:
    balance peaks at 1500 then ends at 900 (never below 90% of initial —
    no Risk-of-Ruin) for a 40% peak-to-trough drawdown. Exactly half of a
    large, deterministically-alternating run hits each order, so the two
    metrics come out to different, exact values — proving the mutation
    this module's own docstring guards against: collapsing Risk of Ruin
    and max-drawdown-percentile into the same number."""
    loss_then_win = [-600.0, 500.0]
    win_then_loss = [500.0, -600.0]
    trades = [_trade(-600.0), _trade(500.0)]
    rng = _AlternatingOrderRng(loss_then_win, win_then_loss)

    result = run_monte_carlo_simulation(
        trades, _INITIAL_BALANCE, iterations=1000, rng=rng
    )

    assert result.risk_of_ruin_50_percent == pytest.approx(50.0)
    assert result.risk_of_ruin_100_percent == pytest.approx(0.0)
    assert result.p95_max_drawdown_percent == pytest.approx(60.0)
    assert result.p99_max_drawdown_percent == pytest.approx(60.0)
    # The full per-iteration distribution is exposed too, not just its
    # percentiles — the histogram chart needs every value, not a summary.
    assert len(result.max_drawdowns_percent) == 1000
    assert set(result.max_drawdowns_percent) == {40.0, 60.0}


def test_a_single_loss_matching_the_initial_balance_registers_full_ruin_every_path():
    """With one trade there is nothing to shuffle — the account touches
    exactly zero on every simulated path, so both thresholds read an exact
    100%, not a statistical rate."""
    trades = [_trade(-1000.0)]

    result = run_monte_carlo_simulation(
        trades,
        _INITIAL_BALANCE,
        iterations=200,
        rng=Random(7),  # noqa: S311 — determinism, not cryptography
    )

    assert result.risk_of_ruin_100_percent == pytest.approx(100.0)
    assert result.risk_of_ruin_50_percent == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Sample equity curves for the spaghetti chart
# ---------------------------------------------------------------------------


def test_sample_curves_are_capped_independently_of_iteration_count():
    trades = [_trade(10.0), _trade(-5.0), _trade(20.0)]

    result = run_monte_carlo_simulation(
        trades,
        _INITIAL_BALANCE,
        iterations=50,
        rng=Random(3),  # noqa: S311 — determinism, not cryptography
        sample_curve_count=5,
    )

    assert len(result.sample_equity_curves) == 5
    for curve in result.sample_equity_curves:
        # initial balance + one point per trade.
        assert len(curve) == len(trades) + 1
        assert curve[0] == _INITIAL_BALANCE


def test_sample_curves_never_exceed_the_iteration_count():
    trades = [_trade(10.0)]

    result = run_monte_carlo_simulation(
        trades,
        _INITIAL_BALANCE,
        iterations=3,
        rng=Random(3),  # noqa: S311 — determinism, not cryptography
        sample_curve_count=200,
    )

    assert len(result.sample_equity_curves) == 3


# ---------------------------------------------------------------------------
# Determinism — a caller-seeded rng gives a reproducible result
# ---------------------------------------------------------------------------


def test_the_same_seed_reproduces_the_same_result():
    trades = [_trade(30.0), _trade(-40.0), _trade(15.0), _trade(-10.0)]

    first = run_monte_carlo_simulation(
        trades,
        _INITIAL_BALANCE,
        iterations=300,
        rng=Random(99),  # noqa: S311 — determinism, not cryptography
    )
    second = run_monte_carlo_simulation(
        trades,
        _INITIAL_BALANCE,
        iterations=300,
        rng=Random(99),  # noqa: S311 — determinism, not cryptography
    )

    assert first == second
