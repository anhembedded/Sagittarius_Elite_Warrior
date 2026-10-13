"""`EPIC-029C` — the planner end to end: parameters in, plan, derived values and verdicts out.

One function, so the Bots tab (`EPIC-029F`), the backtest (`EPIC-029D`) and
`GridKind.validate` all judge the same parameters the same way.

Parameters the user has not set yet (a new bot carries none, `BOT-150`) are
one REFUSED `PARAMETERS_NOT_SET` naming them in the user's words, and no plan.
Parameters that cannot be read are not a check's verdict but the absence of a
plan: they come back as a single REFUSED `PARAMETERS_UNREADABLE` naming the
key (or, for a number too large to compute with, the arithmetic error), and no
plan. More grids than may be open is `TOO_MANY_LEVELS`, judged before the
ladder is built. `validate` never raises on bad input.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_grid_checks import (
    judge_futures_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_constraints import (
    run_checks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_derived import (
    GridDerived,
    derive,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exposure_check import (
    exposure_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
    unset_parameters,
    unset_parameters_reason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.intended_setting import (
    intended_setting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.level_sizing_rule import (
    level_sizing_for,
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


def evaluate_grid(
    inputs: BotKindInputs,
    thresholds: GridThresholds,
    level_sizing: LevelSizing | None = None,
) -> GridEvaluation:
    """@param level_sizing How the levels are sized; by default the venue's: a position
    venue's levels all have one quantity (`level_sizing_for` its exposure kind)."""
    unset = unset_parameters(inputs.config)
    if unset:
        return _not_set(unset)
    try:
        params = GridParams.from_config(inputs.config)
    except GridParamsError as exc:
        return _unreadable(str(exc))
    refusal = exposure_refusal(params, inputs.limits)
    if refusal is not None:
        return GridEvaluation((refusal,), params)
    if params.grid_count > inputs.terms.max_open_orders:
        return GridEvaluation((_too_many_levels(params, inputs),), params)
    try:
        sizing = level_sizing or level_sizing_for(inputs.limits.exposure_kind)
        grid_plan = plan(params, inputs.terms, inputs.market.last_price, sizing)
        derived = derive(params, inputs.terms, grid_plan)
        check_inputs = GridCheckInputs(
            params,
            grid_plan,
            derived,
            inputs.terms,
            inputs.market,
            thresholds,
            inputs.account,
        )
        verdicts = run_checks(check_inputs) + _risk_verdicts(
            inputs, thresholds, params, grid_plan
        )
    except ArithmeticError as exc:
        return _unreadable(f"a value is out of range ({type(exc).__name__})")
    return GridEvaluation(verdicts, params, grid_plan, derived)


def _risk_verdicts(
    inputs: BotKindInputs,
    thresholds: GridThresholds,
    params: GridParams,
    plan: GridPlan,
) -> tuple[Verdict, ...]:
    """The liquidation verdicts of a plan on a position venue, once its facts are read
    (`EPIC-039F`, shown by `EPIC-039J`); nothing for a venue that supplies none. The symbol is
    judged on the setting the gate will make (`intended_setting`), as Start's guard does."""
    risk = inputs.risk
    if risk is None:
        return ()
    return judge_futures_plan(
        PlanRiskInputs(
            params,
            plan,
            intended_setting(risk.setting, params, risk.brackets),
            risk.brackets,
            inputs.market.last_price,
            thresholds.futures,
            inputs.market.daily_atr,
        )
    )


def _not_set(labels: tuple[str, ...]) -> GridEvaluation:
    return GridEvaluation(
        (
            Verdict(
                VerdictSeverity.REFUSED,
                "PARAMETERS_NOT_SET",
                unset_parameters_reason(labels),
            ),
        )
    )


def _unreadable(reason: str) -> GridEvaluation:
    return GridEvaluation(
        (
            Verdict(
                VerdictSeverity.REFUSED,
                "PARAMETERS_UNREADABLE",
                f"The Grid parameters cannot be read: {reason}",
            ),
        )
    )


def _too_many_levels(params: GridParams, inputs: BotKindInputs) -> Verdict:
    """At least `grid_count` levels hold an order (one may stay EMPTY)."""
    allowed = inputs.terms.max_open_orders
    return Verdict(
        VerdictSeverity.REFUSED,
        "TOO_MANY_LEVELS",
        f"{params.grid_count} grids place at least {params.grid_count} orders; "
        f"at most {allowed} may be open",
        {"orders": Decimal(params.grid_count), "max_open_orders": Decimal(allowed)},
    )
