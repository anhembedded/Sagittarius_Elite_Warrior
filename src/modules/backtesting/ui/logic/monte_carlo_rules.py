"""`BOT-107B` — pure logic for the Monte Carlo panel: the headline statistics
as a read-out of raw values (`AppValueFormatter` writes them, `EPIC-033N`), the
max-drawdown histogram buckets, and the spaghetti-chart point series. No I/O and no Qt here — `monte_carlo_panel.py`
and the two chart widgets are the only consumers, matching the
`logic/*_rules.py` + view/widget split every other modal in this package
already uses (`out_of_sample_comparison_rules.py`, `report_comparison_rules.py`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monte_carlo_simulation import (
    MonteCarloSimulationResult,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
)

DEFAULT_HISTOGRAM_BUCKET_COUNT = 20


@dataclass(frozen=True)
class DrawdownHistogramBucket:
    """One bar of the max-drawdown probability distribution chart."""

    range_start: float
    range_end: float
    count: int


_ITERATIONS = "iterations"
_MEDIAN_RETURN = "median_return"
_P95_DRAWDOWN = "p95_drawdown"
_P99_DRAWDOWN = "p99_drawdown"
_RUIN_HALF = "ruin_half"
_RUIN_TOTAL = "ruin_total"

#: The rows of the summary, in the order the task itself lists them: median
#: return, then the two drawdown percentiles, then the two Risk-of-Ruin
#: thresholds. What a threshold means sits in its title, where a unit would.
_SUMMARY_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(_ITERATIONS, "Simulations run", ColumnKind.QUANTITY),
    ColumnSpec(_MEDIAN_RETURN, "Median expected return", ColumnKind.PERCENT),
    ColumnSpec(_P95_DRAWDOWN, "Worst-case drawdown (p95)", ColumnKind.PERCENT),
    ColumnSpec(_P99_DRAWDOWN, "Worst-case drawdown (p99)", ColumnKind.PERCENT),
    ColumnSpec(
        _RUIN_HALF,
        "Risk of ruin (account below 50% of starting capital)",
        ColumnKind.PERCENT,
    ),
    ColumnSpec(_RUIN_TOTAL, "Risk of ruin (total loss)", ColumnKind.PERCENT),
)


def build_summary_readout(result: MonteCarloSimulationResult) -> Readout:
    """The headline statistics, raw: the panel's `ReadoutSlot` writes them."""
    return Readout(
        _SUMMARY_SPECS,
        {
            _ITERATIONS: result.iterations,
            _MEDIAN_RETURN: result.median_return_percent,
            _P95_DRAWDOWN: result.p95_max_drawdown_percent,
            _P99_DRAWDOWN: result.p99_max_drawdown_percent,
            _RUIN_HALF: result.risk_of_ruin_50_percent,
            _RUIN_TOTAL: result.risk_of_ruin_100_percent,
        },
    )


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
