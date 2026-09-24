"""`BOT-115D` — pure comparison logic for the "compare 2 reports" dialog:
the config-diff text, the metrics side-by-side rows and their tone, the
market-mismatch warning, and the two equity curves normalized onto one
scale. No I/O and no Qt here — `report_comparison_dialog.py` is the only
consumer, matching the `logic/*_rules.py` + dialog split every other modal
in this package already uses (`metrics_detail_rules.py`/`metrics_detail_dialog.py`).

@par Reusing `compute_diff_summary()`, not a second comparator
`BacktestRunConfig.compute_diff_summary()` already exists for the
dirty-tracking banner and already names every field this task's own §2.1
asks for. Task §2.1 asks to reuse it "instead of writing a second
comparison logic" — so this module does exactly that rather than
re-deriving a structured per-field diff table, at the cost of the diff
reading as one joined line instead of one row per field. Splitting that
line back into rows would mean parsing it (fragile — some of its own
segments contain a comma, e.g. `f"{value:,.0f}"` for Capital) or duplicating
`compute_diff_summary()`'s own field list a second time, which is exactly
what task §2.1 says not to do.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone

#: Configurations that compare as fully equal produce this exact fallback
#: from `compute_diff_summary()` (its own "diffs list is empty" branch) —
#: shown to the user as a friendlier, explicit message instead.
IDENTICAL_CONFIG_TEXT = "Configurations are identical"

#: `BacktestMetrics` fields where a SMALLER number is the better outcome —
#: task §2.2's own two named examples (`max_drawdown_percent`,
#: `max_consecutive_losses`) plus the one other duration/severity field of
#: the same shape. Every other numeric field defaults to "bigger is better"
#: (true even for the already-negative `gross_loss`/`avg_losing_trade`/
#: `largest_losing_trade` — a loss closer to zero IS the bigger number).
_LOWER_IS_BETTER: frozenset[str] = frozenset(
    {"max_drawdown_percent", "max_consecutive_losses", "max_drawdown_duration_bars"}
)

#: Fields that are informational counts/flags, not a "which side is
#: better" comparison — always shown with a neutral tone regardless of
#: which side's number is bigger.
_NEUTRAL_FIELDS: frozenset[str] = frozenset(
    {
        "total_closed_trades",
        "avg_bars_per_trade",
        "has_high_fee_ratio",
        "has_high_trade_frequency",
    }
)

#: `(field_name, display_label, suffix)` — the metrics rows shown in the
#: comparison table, in display order. A short, curated set (not every
#: `BacktestMetrics` field) matching the metrics `MetricsDetailDialogWidget`
#: already treats as headline figures.
_METRIC_ROWS: tuple[tuple[str, str, str], ...] = (
    ("net_profit", "Net Profit", ""),
    ("net_profit_percent", "Net Profit %", "%"),
    ("max_drawdown_percent", "Max Drawdown", "%"),
    ("percent_profitable", "Win Rate", "%"),
    ("profit_factor", "Profit Factor", ""),
    ("total_closed_trades", "Total Closed Trades", ""),
    ("sharpe_ratio", "Sharpe Ratio", ""),
    ("sortino_ratio", "Sortino Ratio", ""),
    ("max_consecutive_losses", "Max Consecutive Losses", ""),
)

_ZERO_DELTA_TOLERANCE = 1e-9


@dataclass(frozen=True)
class MetricComparisonRow:
    """One row of the side-by-side metrics table."""

    label: str
    value_a: str
    value_b: str
    delta: str
    tone: Tone


def build_config_diff_text(
    config_a: BacktestRunConfig, config_b: BacktestRunConfig
) -> str:
    """The config-diff line shown above the metrics table — see this
    module's own docstring for why it is `compute_diff_summary()`'s output
    verbatim rather than a rebuilt per-field table."""
    if config_a == config_b:
        return IDENTICAL_CONFIG_TEXT
    return config_a.compute_diff_summary(config_b)


def build_market_mismatch_warning(
    config_a: BacktestRunConfig, config_b: BacktestRunConfig
) -> str:
    """Task §3's own required case: comparing across symbols/timeframes is
    still allowed, but must say so rather than silently implying the two
    equity curves are on the same footing."""
    if config_a.symbol != config_b.symbol:
        return (
            f"Comparing different markets: {config_a.symbol} vs "
            f"{config_b.symbol} — metrics are not directly comparable."
        )
    if config_a.timeframe != config_b.timeframe:
        return (
            f"Comparing different timeframes: {config_a.timeframe.value} vs "
            f"{config_b.timeframe.value} — metrics are not directly comparable."
        )
    return ""


def _format_metric_value(value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _row_tone(field_name: str, delta: float) -> Tone:
    if field_name in _NEUTRAL_FIELDS:
        return Tone.NEUTRAL
    if abs(delta) <= _ZERO_DELTA_TOLERANCE:
        return Tone.NEUTRAL
    improved = delta < 0 if field_name in _LOWER_IS_BETTER else delta > 0
    return Tone.POSITIVE if improved else Tone.NEGATIVE


def build_metric_comparison_rows(
    metrics_a: BacktestMetrics, metrics_b: BacktestMetrics
) -> list[MetricComparisonRow]:
    """One row per `_METRIC_ROWS` entry, `metrics_b` relative to
    `metrics_a` — the delta's tone follows `_LOWER_IS_BETTER`/
    `_NEUTRAL_FIELDS` above rather than the raw sign of the difference."""
    rows: list[MetricComparisonRow] = []
    for field_name, label, suffix in _METRIC_ROWS:
        value_a = getattr(metrics_a, field_name)
        value_b = getattr(metrics_b, field_name)
        delta = float(value_b) - float(value_a)
        sign = "+" if delta > 0 else ("" if delta < 0 else "±")
        delta_text = f"{sign}{abs(delta):,.2f}{suffix}" if delta else f"0{suffix}"
        rows.append(
            MetricComparisonRow(
                label=label,
                value_a=f"{_format_metric_value(value_a)}{suffix}",
                value_b=f"{_format_metric_value(value_b)}{suffix}",
                delta=delta_text,
                tone=_row_tone(field_name, delta),
            )
        )
    return rows


def build_equity_comparison_series(
    result_a: BacktestResult, result_b: BacktestResult
) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    """Both curves rebased to "% of starting capital" (100.0 at the first
    point) so two runs with different `initial_balance` still overlay
    meaningfully — task §2.3's own requirement. Takes the two full results
    rather than their `equity_curve`/`initial_balance` separately
    (`code/quality.md` §7 — those two fields are conceptually paired and
    `BacktestResult` already carries them together). Points with a
    non-positive starting balance are returned empty rather than dividing
    by zero/negative (never a real backtest input, but not this function's
    job to raise over)."""
    return (
        _normalize_to_percent(result_a.equity_curve, result_a.initial_balance),
        _normalize_to_percent(result_b.equity_curve, result_b.initial_balance),
    )


def _normalize_to_percent(
    equity_curve: Sequence[tuple[datetime, float]], initial_balance: float
) -> list[dict[str, float]]:
    if not equity_curve or initial_balance <= 0:
        return []
    return [
        {"t": timestamp.timestamp(), "v": equity / initial_balance * 100.0}
        for timestamp, equity in equity_curve
    ]


def build_loaded_file_label(path: str) -> str:
    """Column B's label after loading a file — basename only, never the
    full path. Same convention as `report_import.py`'s
    `build_imported_report_banner_text()`."""
    return os.path.basename(path)
