"""`EPIC-039B` - a direction or a leverage the venue's profile does not allow is refused.

The inputs carry the venue's `ExposureLimits` (the profile's directions and maximum leverage);
without a venue's word they are the Spot profile's: LONG at 1. A Spot bot, and a definition saved
before the epic, judge as they always did; a Spot definition that names a leverage above 1 is
refused in the user's words and is never planned at the multiplied capital and never clamped.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_LIMITS,
    ExposureLimits,
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

_FUTURES_LIKE = ExposureLimits(frozenset(TradeDirection), 20)


def _with(limits: ExposureLimits | None, **changes: str) -> BotKindInputs:
    base = inputs(**changes)
    if limits is None:
        return base
    return BotKindInputs(base.config, base.terms, base.market, base.account, limits)


def _codes(evaluation) -> set[str]:
    return {v.code for v in evaluation.verdicts}


def test_without_a_venues_word_the_limits_are_the_spot_profiles() -> None:
    assert ExposureLimits(frozenset({TradeDirection.LONG}), 1) == SPOT_LIMITS
    assert inputs().limits == SPOT_LIMITS


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


@pytest.mark.parametrize("leverage", ["2", "3", "20"])
def test_a_spot_definition_with_a_leverage_above_one_is_refused(leverage: str) -> None:
    evaluation = evaluate_grid(
        _with(None, direction="LONG", leverage=leverage), GridThresholds()
    )

    (verdict,) = evaluation.verdicts
    assert verdict.code == "LEVERAGE_NOT_ALLOWED"
    assert verdict.severity is VerdictSeverity.REFUSED
    assert leverage in verdict.reason
    assert "1" in verdict.reason
    assert evaluation.plan is None, "it must not be planned at the multiplied capital"


def test_the_refused_leverage_is_not_clamped() -> None:
    """The user's rule: the bot never fixes a parameter."""
    evaluation = evaluate_grid(
        _with(None, direction="LONG", leverage="3"), GridThresholds()
    )

    assert evaluation.params is not None
    assert evaluation.params.leverage == 3


def test_a_direction_is_refused_before_a_leverage() -> None:
    evaluation = evaluate_grid(
        _with(None, direction="SHORT", leverage="5"), GridThresholds()
    )

    assert _codes(evaluation) == {"DIRECTION_NOT_ALLOWED"}


def test_a_direction_and_a_leverage_the_profile_allows_are_planned() -> None:
    evaluation = evaluate_grid(
        _with(_FUTURES_LIKE, direction="SHORT", leverage="20"), GridThresholds()
    )

    assert evaluation.plan is not None
    assert evaluation.plan.direction is TradeDirection.SHORT
    assert not _codes(evaluation) & {"DIRECTION_NOT_ALLOWED", "LEVERAGE_NOT_ALLOWED"}


def test_one_leverage_over_the_profiles_maximum_is_refused() -> None:
    evaluation = evaluate_grid(
        _with(_FUTURES_LIKE, direction="LONG", leverage="21"), GridThresholds()
    )

    assert _codes(evaluation) == {"LEVERAGE_NOT_ALLOWED"}


def test_a_definition_saved_before_the_epic_is_judged_as_before() -> None:
    evaluation = evaluate_grid(_with(None), GridThresholds())

    assert evaluation.plan is not None
    assert not _codes(evaluation) & {"DIRECTION_NOT_ALLOWED", "LEVERAGE_NOT_ALLOWED"}


def test_a_kind_with_no_ladder_to_judge_never_sees_the_limit() -> None:
    """Parameters not yet set stay `PARAMETERS_NOT_SET`, not a leverage complaint."""
    evaluation = evaluate_grid(
        _with(None, lower="", direction="LONG", leverage="3"), GridThresholds()
    )

    assert _codes(evaluation) == {"PARAMETERS_NOT_SET"}
