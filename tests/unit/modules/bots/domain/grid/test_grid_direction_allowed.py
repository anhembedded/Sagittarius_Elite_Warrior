"""`EPIC-039B` - a direction the venue's profile does not allow is refused, in the user's words.

The inputs carry the directions the venue allows (the profile's `directions`); without a
venue's word they are the Spot profile's, LONG only, so a Spot bot judges as it always did.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)

_ALL = frozenset(TradeDirection)


def _with(allowed: frozenset[TradeDirection] | None, **changes: str) -> BotKindInputs:
    base = inputs(**changes)
    if allowed is None:
        return base
    return BotKindInputs(
        base.config, base.terms, base.market, base.account, allowed_directions=allowed
    )


@pytest.mark.parametrize("direction", ["SHORT", "NEUTRAL"])
def test_a_direction_the_spot_profile_does_not_allow_is_refused(direction: str) -> None:
    evaluation = evaluate_grid(
        _with(None, direction=direction, leverage="1"), GridThresholds()
    )

    (verdict,) = evaluation.verdicts
    assert verdict.code == "DIRECTION_NOT_ALLOWED"
    assert verdict.severity is VerdictSeverity.REFUSED
    assert direction.lower() in verdict.reason.lower()
    assert "long" in verdict.reason.lower()
    assert evaluation.plan is None


def test_a_direction_the_profile_allows_is_planned() -> None:
    evaluation = evaluate_grid(
        _with(_ALL, direction="SHORT", leverage="2"), GridThresholds()
    )

    assert evaluation.plan is not None
    assert "DIRECTION_NOT_ALLOWED" not in {v.code for v in evaluation.verdicts}
    assert evaluation.plan.direction is TradeDirection.SHORT


def test_a_definition_saved_before_the_epic_is_judged_as_before() -> None:
    evaluation = evaluate_grid(_with(None), GridThresholds())

    assert evaluation.plan is not None
    assert "DIRECTION_NOT_ALLOWED" not in {v.code for v in evaluation.verdicts}
