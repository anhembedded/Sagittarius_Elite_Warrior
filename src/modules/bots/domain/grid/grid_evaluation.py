"""`EPIC-029C` — the planner end to end: parameters in, plan, derived values and verdicts out.

One function, so the Bots tab (`EPIC-029F`), the backtest (`EPIC-029D`) and
`GridKind.validate` all judge the same parameters the same way.

Parameters that cannot be read are not a check's verdict but the absence of a
plan: they come back as a single REFUSED `PARAMETERS_UNREADABLE` naming the
key, and no plan. `validate` never raises on bad input.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_checks import (
    GridCheckInputs,
    run_checks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_derived import (
    GridDerived,
    derive,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)


@dataclass(frozen=True, slots=True)
class GridEvaluation:
    """A plan with what it implies and what the checks say, or only the refusal."""

    verdicts: tuple[Verdict, ...]
    params: GridParams | None = None
    plan: GridPlan | None = None
    derived: GridDerived | None = None


def evaluate_grid(inputs: BotKindInputs, thresholds: GridThresholds) -> GridEvaluation:
    try:
        params = GridParams.from_config(inputs.config)
    except GridParamsError as exc:
        return GridEvaluation(
            (
                Verdict(
                    VerdictSeverity.REFUSED,
                    "PARAMETERS_UNREADABLE",
                    f"The Grid parameters cannot be read: {exc}",
                ),
            )
        )
    grid_plan = plan(params, inputs.terms, inputs.market.last_price)
    derived = derive(params, inputs.terms, grid_plan)
    check_inputs = GridCheckInputs(
        params, grid_plan, derived, inputs.terms, inputs.market, thresholds
    )
    return GridEvaluation(run_checks(check_inputs), params, grid_plan, derived)
