"""`EPIC-040D` — what the result panes draw for one outcome, built from the run that made it."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    OutcomeShown,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.outcome_view import (
    chart_candles,
    figure_readout,
    result_overlay,
)


def outcome_shown(
    outcome: BacktestOutcome,
    request: KindBacktestRequest,
    plan: SandboxPlan,
    kind: IBotKind | None,
) -> OutcomeShown:
    """The overlay is the kind's, drawn only when the request carried the terms it needs."""
    overlay = BotOverlay()
    if kind is not None:
        overlay = result_overlay(kind, plan, request.terms, outcome)
    return OutcomeShown(
        chart_candles(outcome, request.symbol, request.interval),
        overlay,
        outcome.equity,
        figure_readout(outcome),
        outcome.notes,
        outcome.fills,
    )
