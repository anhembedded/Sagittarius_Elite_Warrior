"""`EPIC-039B` - a Grid asks no more of its venue than the venue's profile allows.

One function, so the planner's verdicts, the backtest and the check Start repeats refuse the
same way. A direction or a leverage outside the venue's `ExposureLimits` is a REFUSED verdict
in the user's words; it is never clamped (the bot judges the user's parameters, it does not
fix them) and the Grid is never planned at a capital the venue would not let it reach.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    RangeExit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)


def exposure_refusal(params: GridParams, limits: ExposureLimits) -> Verdict | None:
    """The refusal for a direction, leverage or range exit outside `limits`, else `None`.

    A direction is judged before a leverage, and both before the range exit: one sentence per
    definition.
    """
    if params.direction not in limits.directions:
        allowed = ", ".join(sorted(d.value for d in limits.directions))
        return Verdict(
            VerdictSeverity.REFUSED,
            "DIRECTION_NOT_ALLOWED",
            f"A {params.direction.value} grid cannot run on this venue; it allows: {allowed}",
        )
    if params.leverage > limits.max_leverage:
        return Verdict(
            VerdictSeverity.REFUSED,
            "LEVERAGE_NOT_ALLOWED",
            f"A leverage of {params.leverage} is not available on this venue; "
            f"the most it allows is {limits.max_leverage}",
        )
    if (
        params.on_range_exit is RangeExit.CLOSE
        and limits.exposure_kind is not ExposureKind.POSITION
    ):
        return Verdict(
            VerdictSeverity.REFUSED,
            "RANGE_EXIT_NOT_ALLOWED",
            "Closing when the price leaves the range is for a position venue; "
            "a Spot grid holds what it bought out of range",
        )
    return None
