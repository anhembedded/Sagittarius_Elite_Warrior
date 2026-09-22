"""`calculate_drawdown_series` — the full running peak-to-trough drawdown
curve, for the underwater chart `BOT-106C` describes.

@details `BacktestMetrics.compute()` (`backtest_metrics.py`) already computes
this exact running-peak drawdown definition, but reduces it to a single
number (`max_drawdown_percent`) — the visualization needs the whole curve,
one point per `equity_curve` point. Same definition, not a second one:
`max(v for _, v in calculate_drawdown_series(curve))` equals
`BacktestMetrics.compute(...).max_drawdown_percent` for the same curve
(locked by this module's own test).
"""

from __future__ import annotations

from datetime import datetime


def calculate_drawdown_series(
    equity_curve: list[tuple[datetime, float]],
) -> list[tuple[datetime, float]]:
    """One `(time, drawdown_percent)` point per `equity_curve` point —
    `drawdown_percent` is the percent drop from the running peak equity seen
    so far, `0.0` at every new high."""
    if not equity_curve:
        return []

    peak = equity_curve[0][1]
    series: list[tuple[datetime, float]] = []
    for time, equity in equity_curve:
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak * 100 if peak else 0.0
        series.append((time, drawdown))
    return series
