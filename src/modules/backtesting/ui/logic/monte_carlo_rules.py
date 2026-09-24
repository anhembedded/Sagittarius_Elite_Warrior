"""`BOT-107B` — pure formatting/bucketing logic for the Monte Carlo dialog:
the headline-statistics text, the max-drawdown histogram buckets, and the
spaghetti-chart point series. No I/O and no Qt here — `monte_carlo_dialog.py`
and the two chart widgets are the only consumers, matching the
`logic/*_rules.py` + dialog/widget split every other modal in this package
already uses (`out_of_sample_comparison_rules.py`, `report_comparison_rules.py`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monte_carlo_simulation import (
    MonteCarloSimulationResult,
)

DEFAULT_HISTOGRAM_BUCKET_COUNT = 20


@dataclass(frozen=True)
class DrawdownHistogramBucket:
    """One bar of the max-drawdown probability distribution chart."""

    range_start: float
    range_end: float
    count: int


def build_summary_lines(result: MonteCarloSimulationResult) -> list[str]:
    """One line per headline statistic, in the order the task itself lists
    them: median return, then the two drawdown percentiles, then the two
    Risk-of-Ruin thresholds."""
    sign = "+" if result.median_return_percent >= 0 else ""
    return [
        f"Simulations run: {result.iterations:,}",
        f"Median Expected Return: {sign}{result.median_return_percent:.2f}%",
        (
            f"p95 / p99 Worst-Case Drawdown: "
            f"{result.p95_max_drawdown_percent:.2f}% / "
            f"{result.p99_max_drawdown_percent:.2f}%"
        ),
        (
            f"Risk of Ruin: {result.risk_of_ruin_50_percent:.2f}% "
            f"(account fell below 50% of starting capital) · "
            f"{result.risk_of_ruin_100_percent:.2f}% (total loss)"
        ),
    ]


def build_drawdown_histogram_buckets(
    max_drawdowns_percent: Sequence[float],
    bucket_count: int = DEFAULT_HISTOGRAM_BUCKET_COUNT,
) -> list[DrawdownHistogramBucket]:
    """Buckets the whole max-drawdown distribution into `bucket_count`
    equal-width ranges from 0 to the worst observed drawdown — `0` is
    always the left edge (a path with no drawdown at all is a real,
    meaningful outcome, not something to crop out of the chart)."""
    if not max_drawdowns_percent:
        return []
    worst = max(max_drawdowns_percent)
    if worst <= 0:
        return [DrawdownHistogramBucket(0.0, 0.0, len(max_drawdowns_percent))]
    bucket_width = worst / bucket_count
    counts = [0] * bucket_count
    for value in max_drawdowns_percent:
        index = min(int(value / bucket_width), bucket_count - 1)
        counts[index] += 1
    return [
        DrawdownHistogramBucket(
            range_start=index * bucket_width,
            range_end=(index + 1) * bucket_width,
            count=count,
        )
        for index, count in enumerate(counts)
    ]


def build_spaghetti_chart_series(
    sample_equity_curves: Sequence[tuple[float, ...]],
) -> list[list[dict[str, float]]]:
    """One point list per sampled path, `x` the trade index (`0` is
    `initial_balance`, before any trade), `y` the running balance — a
    plain trade-index axis, not a date axis: a shuffled path's per-trade
    timestamps have no real chronological meaning."""
    return [
        [{"x": float(index), "y": value} for index, value in enumerate(curve)]
        for curve in sample_equity_curves
    ]
