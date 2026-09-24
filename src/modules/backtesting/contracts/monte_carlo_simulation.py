"""`run_monte_carlo_simulation` — `BOT-107B`'s trade-reshuffling robustness
check: does this strategy's edge survive a different order of the same
trades, or did it get lucky on the one sequence the market happened to
deliver?

@par Two distinct risk numbers, on purpose
`risk_of_ruin_*_percent` and `p95`/`p99_max_drawdown_percent` answer
different questions and must not collapse into one: Risk of Ruin is the
classic (Vince) definition — the fraction of simulated paths whose equity
ever falls to a fraction of the STARTING balance — while max drawdown is
the existing peak-to-trough definition `BacktestMetrics`/
`drawdown_series_calculator.py` already use for the real run, computed here
per shuffled path so its distribution's 95th/99th percentile can be read.
Reusing one number for both would silently answer only one of the task's
two questions.

@par Trade Reshuffling only — bootstrap-with-replacement deferred
The task's own heading ("Trade Reshuffling / Xáo trộn Thứ tự Lệnh") and its
mechanism (`sampling with/without replacement`) name two candidate
methods; this module builds the one the heading names — a random
permutation of the same closed trades, sampled without replacement, run
`iterations` times. A bootstrap variant (sampling the same trade pool WITH
replacement, so a path can repeat or omit trades) is a real, comparably-
sized second technique, not a one-line branch of this one — it changes how
many trades a path contains and needs its own distribution question
answered (does the strategy still look reasonable if a lucky trade shows up
twice, or an unlucky one is skipped?). Deferred rather than built
speculatively (`architecture-rule.md` §7.2.1): a `sampling` parameter would
just be plumbing until a real second variant exists.

@par No re-run of the engine
Every `Trade` already carries its fully realized `pnl` (`trade.py`'s own
docstring: "only ever represents a *closed* trade... an unambiguous, fully
realized PnL"), so a shuffled equity curve is just a running sum over a
reordered `pnl` sequence — no `PaperExchange`/engine involvement, and no
market data needed.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from .trade import Trade

#: `BOT-107B` — the classic (Vince) Risk-of-Ruin thresholds: has the account
#: ever fallen to half, or all, of its STARTING balance during a simulated
#: path. Deliberately relative to the starting balance, not the running
#: peak — that peak-relative question is `max_drawdown_percent`'s job.
_RUIN_50_BALANCE_FRACTION = 0.5
_RUIN_100_BALANCE_FRACTION = 0.0

#: How many of the `iterations` simulated equity curves are retained in
#: full for the spaghetti chart. Bounded independently of `iterations`
#: (which can be 10,000) so memory stays proportional to what one chart can
#: actually show, not to simulation count.
DEFAULT_SAMPLE_CURVE_COUNT = 200


@dataclass(frozen=True)
class MonteCarloSimulationResult:
    """One completed Monte Carlo run's aggregate statistics plus a bounded
    sample of full equity paths for the spaghetti chart."""

    iterations: int
    median_return_percent: float
    p95_max_drawdown_percent: float
    p99_max_drawdown_percent: float
    risk_of_ruin_50_percent: float
    risk_of_ruin_100_percent: float
    #: One value per iteration — kept in full (unlike the equity curves
    #: below) so the UI can bucket the whole distribution for the
    #: max-drawdown probability chart, not just its 95th/99th percentile.
    max_drawdowns_percent: tuple[float, ...]
    #: Each inner tuple is one simulated path's equity, `initial_balance`
    #: first, one value per trade after that — at most
    #: `min(iterations, sample_curve_count)` of them.
    sample_equity_curves: tuple[tuple[float, ...], ...]


def run_monte_carlo_simulation(
    trades: Sequence[Trade],
    initial_balance: float,
    iterations: int,
    rng: Random,
    sample_curve_count: int = DEFAULT_SAMPLE_CURVE_COUNT,
) -> MonteCarloSimulationResult:
    """Shuffles `trades`' realized `pnl` values `iterations` times and
    reports the resulting risk distribution. `rng` is an explicit,
    caller-owned `random.Random` — never the `random` module's global
    state — so a test can seed it and get a reproducible result."""
    if not trades:
        raise ValueError("Monte Carlo simulation requires at least one closed trade")
    if iterations < 1:
        raise ValueError("Monte Carlo simulation requires at least one iteration")

    pnls = [trade.pnl for trade in trades]
    final_returns_percent: list[float] = []
    max_drawdowns_percent: list[float] = []
    ruin_50_count = 0
    ruin_100_count = 0
    sample_curves: list[tuple[float, ...]] = []
    sample_count = min(sample_curve_count, iterations)

    shuffled = list(pnls)
    for iteration in range(iterations):
        rng.shuffle(shuffled)
        keep_curve = iteration < sample_count
        balance, min_balance, max_drawdown, curve = _walk_path(
            shuffled, initial_balance, keep_curve=keep_curve
        )
        final_returns_percent.append(
            (balance - initial_balance) / initial_balance * 100
        )
        max_drawdowns_percent.append(max_drawdown)
        if min_balance <= initial_balance * _RUIN_50_BALANCE_FRACTION:
            ruin_50_count += 1
        if min_balance <= initial_balance * _RUIN_100_BALANCE_FRACTION:
            ruin_100_count += 1
        if curve is not None:
            sample_curves.append(curve)

    return MonteCarloSimulationResult(
        iterations=iterations,
        median_return_percent=statistics.median(final_returns_percent),
        p95_max_drawdown_percent=_percentile(max_drawdowns_percent, 95.0),
        p99_max_drawdown_percent=_percentile(max_drawdowns_percent, 99.0),
        risk_of_ruin_50_percent=ruin_50_count / iterations * 100,
        risk_of_ruin_100_percent=ruin_100_count / iterations * 100,
        max_drawdowns_percent=tuple(max_drawdowns_percent),
        sample_equity_curves=tuple(sample_curves),
    )


def _walk_path(
    shuffled_pnls: Sequence[float],
    initial_balance: float,
    *,
    keep_curve: bool,
) -> tuple[float, float, float, tuple[float, ...] | None]:
    """One shuffled path's final balance, minimum balance reached (for
    Risk of Ruin), peak-to-trough max drawdown percent, and — only when
    `keep_curve` — the full equity curve for the spaghetti chart."""
    balance = initial_balance
    peak = initial_balance
    min_balance = initial_balance
    max_drawdown = 0.0
    curve = [initial_balance] if keep_curve else None
    for pnl in shuffled_pnls:
        balance += pnl
        if curve is not None:
            curve.append(balance)
        peak = max(peak, balance)
        min_balance = min(min_balance, balance)
        if peak > 0:
            drawdown = (peak - balance) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
    return (
        balance,
        min_balance,
        max_drawdown,
        (tuple(curve) if curve is not None else None),
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    """Linear-interpolation percentile (numpy's default 'linear' method),
    self-contained so this module needs no numpy dependency."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = percentile / 100 * (len(ordered) - 1)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = rank - lower_index
    return (
        ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction
    )
