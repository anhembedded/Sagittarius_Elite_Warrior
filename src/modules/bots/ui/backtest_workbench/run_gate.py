"""`EPIC-040D` — why Run is off, in words, or `""` when it is on.

@details The order is the order a person fixes things in: select a bot, answer the question about
their edits, wait for the market numbers, wait for the leverage brackets a position venue's
liquidation price needs, then change the parameters the kind refuses. The market numbers and risk
facts are the sandbox's own bot's (`world`), never the selected bot's."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench import (
    workbench_words as words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.sandbox_editing import (
    SandboxEditing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
    needs_brackets,
)


def reason_run_is_off(
    selection: WorkbenchSelection, world: WorkbenchSelection, sandbox: SandboxEditing
) -> str:
    plan = sandbox.plan
    if selection.bot is None or plan is None:
        return words.NO_BOT
    if sandbox.pending_copy is not None:
        return words.ANSWER_FIRST
    market = world.market
    if market is None or market.terms is None:
        return words.NO_TERMS
    if needs_brackets(plan.venue) and (
        world.risk is None or world.risk.brackets is None
    ):
        return words.NO_BRACKETS
    refused = next((v for v in sandbox.verdicts if v.refuses), None)
    return words.refused_plan(refused.reason) if refused is not None else ""
