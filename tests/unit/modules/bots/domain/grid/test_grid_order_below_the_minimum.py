"""`EPIC-039B` - a level whose quantity cannot be sent is refused, never skipped.

With equal quantity (`LevelSizing.EQUAL_QUANTITY`) one `q` serves every level, so a capital
too small for the step leaves `q` at zero and one too small for the exchange minimum leaves it
worth less than that. Either is one REFUSED `LEVEL_BELOW_MIN_NOTIONAL` from `evaluate_grid`,
whichever sizing is asked; the zero case used to end in a division by zero that the planner
reported as unreadable parameters.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)

_FUTURES_LIKE = ExposureLimits(frozenset(TradeDirection), 20)


def _for(capital: str, step: str = "0.001", **changes: str) -> BotKindInputs:
    base = inputs(capital_quote=capital, **changes)
    return BotKindInputs(
        base.config,
        replace(base.terms, step_size=Decimal(step)),
        base.market,
        limits=_FUTURES_LIKE,
    )


@pytest.mark.parametrize("sizing", list(LevelSizing))
def test_a_capital_too_small_for_the_step_is_refused_not_skipped(
    sizing: LevelSizing,
) -> None:
    evaluation = evaluate_grid(
        _for("0.01", direction="NEUTRAL", leverage="1"), GridThresholds(), sizing
    )

    codes = {v.code: v.severity for v in evaluation.verdicts}
    assert codes["LEVEL_BELOW_MIN_NOTIONAL"] is VerdictSeverity.REFUSED
    assert "PARAMETERS_UNREADABLE" not in codes
    assert evaluation.plan is not None
    assert all(level.quantity == 0 for level in evaluation.plan.order_levels)


@pytest.mark.parametrize("direction", ["LONG", "SHORT", "NEUTRAL"])
def test_an_order_worth_less_than_the_minimum_is_refused_for_every_direction(
    direction: str,
) -> None:
    """q > 0 but, after the step, worth under the 5 minimum."""
    evaluation = evaluate_grid(
        _for("30", direction=direction, leverage="1"),
        GridThresholds(),
        LevelSizing.EQUAL_QUANTITY,
    )

    refused = [v for v in evaluation.verdicts if v.severity is VerdictSeverity.REFUSED]
    assert "LEVEL_BELOW_MIN_NOTIONAL" in {v.code for v in refused}


def test_a_capital_that_clears_the_minimum_is_not_refused_for_it() -> None:
    evaluation = evaluate_grid(
        _for("10000", direction="NEUTRAL", leverage="1"),
        GridThresholds(),
        LevelSizing.EQUAL_QUANTITY,
    )

    assert "LEVEL_BELOW_MIN_NOTIONAL" not in {v.code for v in evaluation.verdicts}
