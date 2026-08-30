"""`ExtendedMetricsSnapshot` — the boundary type between `BackTestPresenter`
and `MetricsDetailPanel`'s screen wiring (`EPIC-015` Phase 3).

@details `MetricsDetailVM` needs `StatCardData` objects plus a handful of raw
`BacktestMetrics` figures (`architecture-rule.md` §2.1: a cross-boundary
contract must be a named type, not a bag of loose values passed around by
convention). `BackTestViewModel.extendedStatCards` cannot serve that role —
it is already `stat_cards_to_qml()`'s dict-ified `list[dict[str, str]]`,
built for QML `Repeater` bindings, with no numeric fields and no
`StatCardData` identity left to read `.value_tone`/`.badge_tone` from. This
type is what `BackTestPresenter._on_backtest_succeeded` retains instead,
right alongside (not in place of) the existing QML-facing dict conversion.

Frozen and plain data — no behaviour belongs here. `BackTestViewModel` holds
one of these as a private attribute and returns it through a plain Python
accessor (not a QML `Property`): only `MetricsDetailDialogWidget`'s
composition root reads it, never a `.qml` file.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.performance_metrics_view import (
    StatCardData,
)


@dataclass(frozen=True)
class ExtendedMetricsSnapshot:
    """Everything `MetricsDetailVM` needs from one finished `BacktestResult`,
    captured once rather than re-derived (`build_extended_stat_cards(result)`
    already ran for `BackTestViewModel.extendedStatCards` — this is that same
    call's output, not a second one)."""

    cards: Sequence[StatCardData]
    gross_profit: float
    gross_loss: float
    profit_factor: float
    total_closed_trades: int
    #: The commission actually applied to THIS run, not whatever the toolbar
    #: currently shows — see `BacktestMetricsDetailSource`'s docstring
    #: (`backtest_modals/backtest_metrics_detail_source.py`) for where the
    #: presenter reads this from and why.
    fee_rate_percent: float
